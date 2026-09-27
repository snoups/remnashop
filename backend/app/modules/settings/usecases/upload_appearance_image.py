import math
from dataclasses import dataclass
from typing import Final

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import AppearanceImageFormat, AppearanceImageKind
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.image import matches_image_magic_bytes, read_image_size, read_svg_size
from app.modules.settings.appearance_storage import delete_appearance_image, save_appearance_image
from app.modules.settings.dto import AppearanceSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class _ImageLimits:
    min_side: int
    max_side: int
    max_bytes: int


_LIMITS_BY_KIND: Final[dict[AppearanceImageKind, _ImageLimits]] = {
    AppearanceImageKind.LOGO: _ImageLimits(min_side=128, max_side=1024, max_bytes=1024 * 1024),
    AppearanceImageKind.FAVICON: _ImageLimits(min_side=32, max_side=512, max_bytes=256 * 1024),
}

# Read cap for the upload route; the per-kind limit is enforced below.
MAX_APPEARANCE_IMAGE_SIZE_BYTES: Final[int] = max(
    limits.max_bytes for limits in _LIMITS_BY_KIND.values()
)

_FORMAT_BY_CONTENT_TYPE: Final[dict[str, AppearanceImageFormat]] = {
    "image/jpeg": AppearanceImageFormat.JPG,
    "image/png": AppearanceImageFormat.PNG,
    "image/webp": AppearanceImageFormat.WEBP,
    "image/svg+xml": AppearanceImageFormat.SVG,
}


@dataclass(frozen=True, kw_only=True)
class UploadAppearanceImageInput:
    content_type: str
    data: bytes


# Vector: no pixel size to range-check, only the aspect ratio.
def _validate_svg(data: bytes) -> None:
    svg_size = read_svg_size(data)
    if svg_size is None:
        raise ValidationError(
            "SVG must be plain markup with a viewBox: no DOCTYPE, scripts or event handlers"
        )
    if not math.isclose(*svg_size, rel_tol=1e-3):
        raise ValidationError("Image must be square")


def _validate_raster(
    data: bytes, image_format: AppearanceImageFormat, limits: _ImageLimits
) -> None:
    if not matches_image_magic_bytes(data, image_format.value):
        raise ValidationError("File content does not match the declared image type")
    size = read_image_size(data)
    if size is None:
        raise ValidationError("Image file is corrupted or unreadable")
    width, height = size
    if width != height:
        raise ValidationError("Image must be square")
    if not limits.min_side <= width <= limits.max_side:
        raise ValidationError(
            f"Image must be between {limits.min_side} and {limits.max_side} px per side"
        )


async def _upload_appearance_image(
    settings_repository: SettingsRepository,
    config: AppConfig,
    uow: UnitOfWork,
    kind: AppearanceImageKind,
    data: UploadAppearanceImageInput,
) -> AppearanceSettingsDto:
    limits = _LIMITS_BY_KIND[kind]
    if len(data.data) > limits.max_bytes:
        raise ValidationError(f"Image file is too large (max {limits.max_bytes // 1024} KB)")
    image_format = _FORMAT_BY_CONTENT_TYPE.get(data.content_type)
    if image_format is None:
        raise ValidationError(f"Unsupported image content type: {data.content_type}")
    if image_format == AppearanceImageFormat.SVG:
        _validate_svg(data.data)
    else:
        _validate_raster(data.data, image_format, limits)

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
