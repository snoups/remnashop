import math
from dataclasses import dataclass
from typing import Final

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import AppearanceImageFormat, AppearanceImageKind
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import EventPublisher
from app.core.utils.image import matches_image_magic_bytes, read_image_size, read_svg_size
from app.modules.settings.appearance_storage import delete_appearance_image, save_appearance_image
from app.modules.settings.dto import AppearanceSettingsDto, UploadAppearanceImageDto
from app.modules.settings.events import AppearanceSettingsChangedEvent
from app.modules.settings.repository import SettingsRepository


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


# Vector: no pixel size to range-check, only the aspect ratio.
def _validate_svg(data: bytes) -> None:
    svg_size = read_svg_size(data)
    if svg_size is None:
        raise ValidationError(
            "SVG must be plain markup with a viewBox: no DOCTYPE, scripts or event handlers",
            code=ErrorCode.SVG_UNSAFE,
        )
    if not math.isclose(*svg_size, rel_tol=1e-3):
        raise ValidationError("Image must be square", code=ErrorCode.IMAGE_NOT_SQUARE)


def _validate_raster(
    data: bytes, image_format: AppearanceImageFormat, limits: _ImageLimits
) -> None:
    if not matches_image_magic_bytes(data, image_format.value):
        raise ValidationError(
            "File content does not match the declared image type",
            code=ErrorCode.IMAGE_CONTENT_MISMATCH,
        )
    size = read_image_size(data)
    if size is None:
        raise ValidationError(
            "Image file is corrupted or unreadable", code=ErrorCode.IMAGE_UNREADABLE
        )
    width, height = size
    if width != height:
        raise ValidationError("Image must be square", code=ErrorCode.IMAGE_NOT_SQUARE)
    if not limits.min_side <= width <= limits.max_side:
        raise ValidationError(
            f"Image must be between {limits.min_side} and {limits.max_side} px per side",
            code=ErrorCode.IMAGE_SIZE_OUT_OF_RANGE,
        )


async def upload_appearance_image(
    settings_repository: SettingsRepository,
    config: AppConfig,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    actor: Actor,
    kind: AppearanceImageKind,
    data: UploadAppearanceImageDto,
) -> AppearanceSettingsDto:
    limits = _LIMITS_BY_KIND[kind]
    if len(data.data) > limits.max_bytes:
        raise ValidationError(
            f"Image file is too large (max {limits.max_bytes // 1024} KB)",
            code=ErrorCode.IMAGE_TOO_LARGE,
        )
    image_format = _FORMAT_BY_CONTENT_TYPE.get(data.content_type)
    if image_format is None:
        raise ValidationError(
            f"Unsupported image content type: {data.content_type}",
            code=ErrorCode.IMAGE_UNSUPPORTED_TYPE,
        )
    if image_format == AppearanceImageFormat.SVG:
        _validate_svg(data.data)
    else:
        _validate_raster(data.data, image_format, limits)

    async with uow:
        existing = await settings_repository.get_appearance_image_meta(kind)
        result = await settings_repository.set_appearance_image(
            kind, data.content_type, image_format.value
        )
        await event_publisher.publish(
            AppearanceSettingsChangedEvent(actor=actor, action=f"{kind.value.lower()}_upload")
        )
    # files change only after the row commits: a failed commit must not
    # leave the row pointing at a file already overwritten or deleted
    save_appearance_image(config.media_dir, kind, image_format.value, data.data)
    if existing is not None and existing[0] != image_format.value:
        delete_appearance_image(config.media_dir, kind, existing[0])
    return result


async def remove_appearance_image(
    settings_repository: SettingsRepository,
    config: AppConfig,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    actor: Actor,
    kind: AppearanceImageKind,
) -> AppearanceSettingsDto:
    async with uow:
        meta = await settings_repository.get_appearance_image_meta(kind)
        if meta is None:
            raise NotFoundError(
                f"Appearance image not set: {kind}", code=ErrorCode.APPEARANCE_IMAGE_NOT_SET
            )
        settings = await settings_repository.clear_appearance_image(kind)
        await event_publisher.publish(
            AppearanceSettingsChangedEvent(actor=actor, action=f"{kind.value.lower()}_delete")
        )
    delete_appearance_image(config.media_dir, kind, meta[0])
    return settings
