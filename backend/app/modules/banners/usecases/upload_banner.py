from dataclasses import dataclass
from typing import Final

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import BannerFormat, BannerName, Locale
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.image import matches_image_magic_bytes
from app.modules.banners.dto import BannerDto, UploadBannerDto
from app.modules.banners.repository import BannerRepository
from app.modules.banners.storage import delete_banner_file, save_banner_file
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto

MAX_BANNER_SIZE_BYTES: Final[int] = 5 * 1024 * 1024

_FORMAT_BY_CONTENT_TYPE: Final[dict[str, BannerFormat]] = {
    "image/jpeg": BannerFormat.JPG,
    "image/png": BannerFormat.PNG,
    "image/gif": BannerFormat.GIF,
    "image/webp": BannerFormat.WEBP,
}


@dataclass(frozen=True, kw_only=True)
class UploadBannerInput:
    name: BannerName
    locale: Locale
    content_type: str
    data: bytes


class UploadBannerUseCase(UseCase[UploadBannerInput, BannerDto]):
    required_permission = Permission.BANNERS_UPLOAD

    def __init__(
        self,
        banner_repository: BannerRepository,
        settings_repository: SettingsRepository,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._banner_repository = banner_repository
        self._settings_repository = settings_repository
        self._config = config
        self._uow = uow

    async def _execute(self, actor: UserDto, data: UploadBannerInput) -> BannerDto:
        async with self._uow:
            banner_format = _FORMAT_BY_CONTENT_TYPE.get(data.content_type)
            if banner_format is None:
                raise ValidationError(f"Unsupported banner content type: {data.content_type}")
            if not matches_image_magic_bytes(data.data, banner_format.value):
                raise ValidationError("File content does not match the declared image type")
            if len(data.data) > MAX_BANNER_SIZE_BYTES:
                raise ValidationError("Banner file is too large")
            active_locales = await self._settings_repository.list_active_locales()
            if data.locale not in active_locales:
                raise ValidationError(f"Locale not enabled: {data.locale}")

            existing = await self._banner_repository.get(data.name, data.locale)

        async with self._uow:
            banner = await self._banner_repository.upsert(
                UploadBannerDto(
                    name=data.name,
                    locale=data.locale,
                    content_type=data.content_type,
                    extension=banner_format.value,
                    size_bytes=len(data.data),
                )
            )
        # Only touch the filesystem once the DB row committed to the new
        # extension -- otherwise a failed commit could leave a row pointing at
        # the old file after we'd already overwritten/deleted it (same
        # extension re-upload writes to the same path as the existing file).
        save_banner_file(
            self._config.media_dir, data.name, data.locale, banner_format.value, data.data
        )
        if existing is not None and existing.extension != banner_format.value:
            delete_banner_file(self._config.media_dir, data.name, data.locale, existing.extension)
        return banner
