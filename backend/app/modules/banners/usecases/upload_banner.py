from typing import Final

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import BannerFormat
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.image import matches_image_magic_bytes
from app.modules.banners.dto import BannerDto, UploadBannerDto, UploadBannerFileDto
from app.modules.banners.events import BannerChangedEvent
from app.modules.banners.repository import BannerRepository
from app.modules.banners.storage import (
    MAX_BANNER_SIZE_BYTES,
    delete_banner_file,
    save_banner_file,
    validate_banner_name,
)
from app.modules.translations import TranslationRepository

_FORMAT_BY_CONTENT_TYPE: Final[dict[str, BannerFormat]] = {
    "image/jpeg": BannerFormat.JPG,
    "image/png": BannerFormat.PNG,
    "image/gif": BannerFormat.GIF,
    "image/webp": BannerFormat.WEBP,
}


class UploadBannerUseCase(UseCase[UploadBannerFileDto, BannerDto]):
    required_permission = Permission.BANNERS_UPLOAD

    def __init__(
        self,
        banner_repository: BannerRepository,
        translation_repository: TranslationRepository,
        config: AppConfig,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._banner_repository = banner_repository
        self._translation_repository = translation_repository
        self._config = config
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UploadBannerFileDto) -> BannerDto:
        try:
            validate_banner_name(data.name)
        except ValueError as err:
            raise ValidationError(str(err), code=ErrorCode.BANNER_NAME_INVALID) from None

        async with self._uow:
            banner_format = _FORMAT_BY_CONTENT_TYPE.get(data.content_type)
            if banner_format is None:
                raise ValidationError(
                    f"Unsupported banner content type: {data.content_type}",
                    code=ErrorCode.BANNER_UNSUPPORTED_TYPE,
                )
            if not matches_image_magic_bytes(data.data, banner_format.value):
                raise ValidationError(
                    "File content does not match the declared image type",
                    code=ErrorCode.IMAGE_CONTENT_MISMATCH,
                )
            if len(data.data) > MAX_BANNER_SIZE_BYTES:
                raise ValidationError("Banner file is too large", code=ErrorCode.BANNER_TOO_LARGE)
            active_locales = await self._translation_repository.list_active_locales()
            if data.locale not in active_locales:
                raise ValidationError(
                    f"Locale not enabled: {data.locale}", code=ErrorCode.LOCALE_NOT_ENABLED
                )

            existing = await self._banner_repository.get(data.name, data.locale)

            banner = await self._banner_repository.upsert(
                UploadBannerDto(
                    name=data.name,
                    locale=data.locale,
                    content_type=data.content_type,
                    extension=banner_format.value,
                    size_bytes=len(data.data),
                )
            )
            await self._event_publisher.publish(
                BannerChangedEvent(
                    actor=actor, action="upload", name=data.name, locale=data.locale.value
                )
            )
        # files change only after the row commits: a failed commit must not
        # leave the row pointing at a file already overwritten or deleted
        save_banner_file(
            self._config.media_dir, data.name, data.locale, banner_format.value, data.data
        )
        if existing is not None and existing.extension != banner_format.value:
            delete_banner_file(self._config.media_dir, data.name, data.locale, existing.extension)
        return banner
