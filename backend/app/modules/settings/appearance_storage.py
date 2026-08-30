from pathlib import Path

from app.core.enums import AppearanceImageKind


def appearance_image_path(media_dir: Path, kind: AppearanceImageKind, extension: str) -> Path:
    return media_dir / "appearance" / f"{kind}.{extension}"


def save_appearance_image(
    media_dir: Path, kind: AppearanceImageKind, extension: str, data: bytes
) -> None:
    path = appearance_image_path(media_dir, kind, extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read_appearance_image(media_dir: Path, kind: AppearanceImageKind, extension: str) -> bytes:
    return appearance_image_path(media_dir, kind, extension).read_bytes()


def delete_appearance_image(media_dir: Path, kind: AppearanceImageKind, extension: str) -> None:
    appearance_image_path(media_dir, kind, extension).unlink(missing_ok=True)
