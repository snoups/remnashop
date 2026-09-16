from dataclasses import dataclass
from typing import Final

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import AppearanceImageFormat, AppearanceImageKind
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.image import matches_image_magic_bytes
from app.modules.settings.appearance_storage import delete_appearance_image, save_appearance_image
from app.modules.settings.dto import AppearanceSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto

MAX_APPEARANCE_IMAGE_SIZE_BYTES: Final[int] = 2 * 1024 * 1024

_FORMAT_BY_CONTENT_TYPE: Final[dict[str, AppearanceImageFormat]] = {
    "image/jpeg": AppearanceImageFormat.JPG,
    "image/png": AppearanceImageFormat.PNG,
    "image/webp": AppearanceImageFormat.WEBP,
}


@dataclass(frozen=True, kw_only=True)
class UploadAppearanceImageInput:
    content_type: str
    data: bytes


async def _upload_appearance_image(
    settings_repository: SettingsRepository,
    config: AppConfig,
    uow: UnitOfWork,
    kind: AppearanceImageKind,
    data: UploadAppearanceImageInput,
) -> AppearanceSettingsDto:
    image_format = _FORMAT_BY_CONTENT_TYPE.get(data.content_type)
    if image_format is None:
        raise ValidationError(f"Unsupported image content type: {data.content_type}")
    if not matches_image_magic_bytes(data.data, image_format.value):
        raise ValidationError("File content does not match the declared image type")
    if len(data.data) > MAX_APPEARANCE_IMAGE_SIZE_BYTES:
        raise ValidationError("Image file is too large")

    async with uow:
        existing = await settings_repository.get_appearance_image_meta(kind)

    save_appearance_image(config.media_dir, kind, image_format.value, data.data)

    async with uow:
        result = await settings_repository.set_appearance_image(
            kind, data.content_type, image_format.value
        )
    # Only drop the old file once the DB row committed to the new one --
    # otherwise a failed commit would leave the row pointing at a file we
    # just deleted.
    if existing is not None and existing[0] != image_format.value:
        delete_appearance_image(config.media_dir, kind, existing[0])
    return result


class UploadAppearanceLogoUseCase(UseCase[UploadAppearanceImageInput, AppearanceSettingsDto]):
    required_permission = Permission.APPEARANCE_LOGO_UPLOAD

    def __init__(
        self, settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork
    ) -> None:
        self._settings_repository = settings_repository
        self._config = config
        self._uow = uow

    async def _execute(
        self, actor: UserDto, data: UploadAppearanceImageInput
    ) -> AppearanceSettingsDto:
        return await _upload_appearance_image(
            self._settings_repository, self._config, self._uow, AppearanceImageKind.LOGO, data
        )


class UploadAppearanceFaviconUseCase(UseCase[UploadAppearanceImageInput, AppearanceSettingsDto]):
    required_permission = Permission.APPEARANCE_FAVICON_UPLOAD

    def __init__(
        self, settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork
    ) -> None:
        self._settings_repository = settings_repository
        self._config = config
        self._uow = uow

    async def _execute(
        self, actor: UserDto, data: UploadAppearanceImageInput
    ) -> AppearanceSettingsDto:
        return await _upload_appearance_image(
            self._settings_repository, self._config, self._uow, AppearanceImageKind.FAVICON, data
        )
