from pathlib import Path


def media_path(media_dir: Path, broadcast_id: int, version: int, extension: str) -> Path:
    return media_dir / "broadcasts" / f"{broadcast_id}_{version}.{extension}"


def save_media(
    media_dir: Path, broadcast_id: int, version: int, extension: str, data: bytes
) -> None:
    path = media_path(media_dir, broadcast_id, version, extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def delete_media(media_dir: Path, broadcast_id: int, version: int, extension: str) -> None:
    media_path(media_dir, broadcast_id, version, extension).unlink(missing_ok=True)
