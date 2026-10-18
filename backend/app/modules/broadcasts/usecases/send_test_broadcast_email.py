from dataclasses import replace

from loguru import logger

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import EmailOutcome
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dto import SendTestBroadcastEmailDto
from app.modules.broadcasts.email_assets import load_email_logo, read_email_images
from app.modules.broadcasts.email_html import email_image_ids
from app.modules.broadcasts.email_render import BroadcastEmailRenderer, unsubscribe_links
from app.modules.broadcasts.render import load_unsubscribe_labels
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.validation import promocode_is_usable
from app.modules.email import EmailSendError, OutgoingEmailDto, SmtpBatchSender, load_email_brand
from app.modules.promocodes import PromocodeRepository
from app.modules.settings import GetPublicAppearanceImageUseCase, SettingsRepository
from app.modules.translations import TranslationRepository
from app.modules.users import UserDto


class SendTestBroadcastEmailUseCase(UseCase[SendTestBroadcastEmailDto, None, UserDto]):
    required_permission = Permission.BROADCASTS_EMAIL_TEST_SEND

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        settings_repository: SettingsRepository,
        promocode_repository: PromocodeRepository,
        translation_repository: TranslationRepository,
        get_public_appearance_image_use_case: GetPublicAppearanceImageUseCase,
        batch_sender: SmtpBatchSender,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._settings_repository = settings_repository
        self._promocode_repository = promocode_repository
        self._translation_repository = translation_repository
        self._get_public_appearance_image_use_case = get_public_appearance_image_use_case
        self._batch_sender = batch_sender
        self._config = config
        self._uow = uow

    async def _execute(self, actor: UserDto, data: SendTestBroadcastEmailDto) -> None:
        async with self._uow:
            broadcast = await self._broadcast_repository.get_by_id(data.broadcast_id)
            if broadcast.default_locale not in broadcast.email_contents:
                raise ValidationError(
                    "The default locale has no email content",
                    code=ErrorCode.BROADCAST_DEFAULT_LOCALE_MISSING,
                )
            profile = (await self._settings_repository.get_email_settings()).profile(bulk=True)
            if not profile.is_configured:
                raise ValidationError("SMTP is not configured", code=ErrorCode.EMAIL_NOT_CONFIGURED)
            context = (await self._broadcast_repository.recipient_contexts([actor.id]))[actor.id]
            code = (
                await promocode_is_usable(self._promocode_repository, broadcast.promocode_id)
                if broadcast.promocode_id is not None
                else None
            )
            labels = await load_unsubscribe_labels(
                self._translation_repository, [data.locale, broadcast.default_locale]
            )
            referenced = set().union(
                *(email_image_ids(c.html) for c in broadcast.email_contents.values())
            )
            image_rows = [
                i
                for i in await self._broadcast_repository.list_email_images(data.broadcast_id)
                if i.id in referenced
            ]
            brand = await load_email_brand(self._settings_repository)

        if referenced - {i.id for i in image_rows}:
            raise ValidationError(
                "Email references an unknown image", code=ErrorCode.BROADCAST_EMAIL_IMAGE_INVALID
            )
        images = await read_email_images(self._config.media_dir, data.broadcast_id, image_rows)
        if images is None:
            raise ValidationError(
                "Email image is missing", code=ErrorCode.BROADCAST_EMAIL_IMAGE_INVALID
            )
        brand, logo = await load_email_logo(self._get_public_appearance_image_use_case, brand)
        cabinet_url = self._config.cabinet.url
        renderer = BroadcastEmailRenderer(
            broadcast,
            promocode_code=code,
            brand=brand,
            unsubscribe=(
                unsubscribe_links(cabinet_url, self._config.crypt_key.get_secret_value())
                if cabinet_url
                else None
            ),
            unsubscribe_labels=labels,
            image_src=lambda i: f"cid:img-{i}",
        )
        rendered = renderer.render(replace(context, language=data.locale), datetime_now())
        attached = [images[i] for i in sorted(rendered.image_ids)]
        if logo is not None and "cid:logo" in rendered.html:
            attached.append(logo)
        email = OutgoingEmailDto(
            to=data.to,
            subject=rendered.subject,
            text=rendered.text,
            html=rendered.html,
            images=attached,
            headers=rendered.headers,
        )
        try:
            async with self._batch_sender.open(profile) as batch:
                result = await batch.send(email)
        except EmailSendError as error:
            raise ValidationError(
                f"Email failed: {error}", code=ErrorCode.BROADCAST_TEST_FAILED
            ) from error
        if result.outcome is not EmailOutcome.SENT:
            raise ValidationError(
                f"Email not sent: {result.error}", code=ErrorCode.BROADCAST_TEST_FAILED
            )
        logger.info(f"{actor.log} Sent test email for broadcast '{data.broadcast_id}'")
