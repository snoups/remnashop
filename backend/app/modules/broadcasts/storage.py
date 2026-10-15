from pathlib import Path
from typing import Final
from uuid import uuid4

from app.core.constants import BROADCAST_MEDIA_MAX_BYTES
from app.core.enums import BroadcastMediaType


def media_path(media_dir: Path, broadcast_id: int, version: int, extension: str) -> Path:
    return media_dir / "broadcasts" / f"{broadcast_id}_{version}.{extension}"


def upload_path(media_dir: Path) -> Path:
    # next to the media, so placing it is a rename on the same filesystem
    return media_dir / "broadcasts" / f".upload-{uuid4().hex}.part"


def place_media(
    media_dir: Path, broadcast_id: int, version: int, extension: str, source: Path
) -> None:
    path = media_path(media_dir, broadcast_id, version, extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    source.replace(path)


def delete_media(media_dir: Path, broadcast_id: int, version: int, extension: str) -> None:
    media_path(media_dir, broadcast_id, version, extension).unlink(missing_ok=True)


_ONE_MB: Final[int] = 1024 * 1024
# content type -> (media type, file extension, size cap)
MEDIA_TYPES: Final[dict[str, tuple[BroadcastMediaType, str, int]]] = {
    "image/jpeg": (BroadcastMediaType.PHOTO, "jpg", 10 * _ONE_MB),
    "image/png": (BroadcastMediaType.PHOTO, "png", 10 * _ONE_MB),
    "image/webp": (BroadcastMediaType.PHOTO, "webp", 10 * _ONE_MB),
    "image/gif": (BroadcastMediaType.ANIMATION, "gif", BROADCAST_MEDIA_MAX_BYTES),
    "video/mp4": (BroadcastMediaType.VIDEO, "mp4", BROADCAST_MEDIA_MAX_BYTES),
    "application/pdf": (BroadcastMediaType.DOCUMENT, "pdf", BROADCAST_MEDIA_MAX_BYTES),
    "application/zip": (BroadcastMediaType.DOCUMENT, "zip", BROADCAST_MEDIA_MAX_BYTES),
}
MEDIA_CONTENT_TYPES: Final[tuple[str, ...]] = tuple(MEDIA_TYPES)
