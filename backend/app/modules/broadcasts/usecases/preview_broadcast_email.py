import base64
from datetime import timedelta
from typing import Final

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dto import (
    PreviewBroadcastEmailDto,
    RecipientContextDto,
    RenderedEmailDto,
)
from app.modules.broadcasts.email_assets import load_email_logo, read_email_images
from app.modules.broadcasts.email_html import email_image_ids
from app.modules.broadcasts.email_render import (
    BroadcastEmailRenderer,
    UnsubscribeLinks,
    unsubscribe_links,
)
from app.modules.broadcasts.render import load_unsubscribe_labels
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.validation import promocode_is_usable
from app.modules.email import InlineImageDto, load_email_brand
from app.modules.promocodes import PromocodeRepository
from app.modules.settings import GetPublicAppearanceImageUseCase, SettingsRepository
from app.modules.translations import TranslationRepository

# the dashboard's Telegram preview shows the same sample customer (TelegramPreview.tsx)
_SAMPLE_PROMOCODE: Final[str] = "PROMO"
_SAMPLE_DAYS: Final[int] = 4
_SAMPLE_NAME_RU: Final[str] = "Анна"
_SAMPLE_NAME: Final[str] = "Anna"
# no cabinet URL yet: the footer still shows; sending is refused until one is set
_PLACEHOLDER_UNSUBSCRIBE: Final[UnsubscribeLinks] = UnsubscribeLinks(
    page=lambda _: "#", one_click=lambda _: "#"
)


def _data_uri(image: InlineImageDto) -> str:
    return f"data:{image.content_type};base64,{base64.b64encode(image.data).decode()}"


class PreviewBroadcastEmailUseCase(UseCase[PreviewBroadcastEmailDto, RenderedEmailDto]):
    required_permission = Permission.BROADCASTS_EMAIL_PREVIEW

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        settings_repository: SettingsRepository,
        promocode_repository: PromocodeRepository,
        translation_repository: TranslationRepository,
        get_public_appearance_image_use_case: GetPublicAppearanceImageUseCase,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._settings_repository = settings_repository
        self._promocode_repository = promocode_repository
        self._translation_repository = translation_repository
        self._get_public_appearance_image_use_case = get_public_appearance_image_use_case
        self._config = config
        self._uow = uow

    async def _execute(self, actor: Actor, data: PreviewBroadcastEmailDto) -> RenderedEmailDto:
        async with self._uow:
            broadcast = await self._broadcast_repository.get_by_id(data.broadcast_id)
            if broadcast.default_locale not in broadcast.email_contents:
                raise ValidationError(
                    "The default locale has no email content",
                    code=ErrorCode.BROADCAST_DEFAULT_LOCALE_MISSING,
                )
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
            promocode_code=code or _SAMPLE_PROMOCODE,
            brand=brand,
            unsubscribe=(
                unsubscribe_links(cabinet_url, self._config.crypt_key.get_secret_value())
                if cabinet_url
                else _PLACEHOLDER_UNSUBSCRIBE
            ),
            unsubscribe_labels=labels,
            image_src=lambda i: _data_uri(images[i]) if i in images else "",
        )
        now = datetime_now()
        rendered = renderer.render(
            RecipientContextDto(
                user_id=0,
                name=_SAMPLE_NAME_RU if data.locale is Locale.RU else _SAMPLE_NAME,
                username="anna",
                language=data.locale,
                bonus_days=3,
                points=120,
                plan_name="Pro",
                expire_at=now + timedelta(days=_SAMPLE_DAYS),
            ),
            now,
        )
        if logo is not None:
            return RenderedEmailDto(
                subject=rendered.subject,
                html=rendered.html.replace("cid:logo", _data_uri(logo)),
                text=rendered.text,
                image_ids=rendered.image_ids,
                headers=rendered.headers,
            )
        return rendered
