from pathlib import Path
from uuid import uuid4


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
