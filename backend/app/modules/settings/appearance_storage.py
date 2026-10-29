from pathlib import Path

from app.core.enums import AppearanceImageKind, AppearanceTarget


# dashboard files stay at the top level, where they lived before the cabinet had its own
def appearance_image_path(
    media_dir: Path, target: AppearanceTarget, kind: AppearanceImageKind, extension: str
) -> Path:
    directory = media_dir / "appearance"
    if target != AppearanceTarget.DASHBOARD:
        directory /= target
    return directory / f"{kind}.{extension}"


def save_appearance_image(
    media_dir: Path,
    target: AppearanceTarget,
    kind: AppearanceImageKind,
    extension: str,
    data: bytes,
) -> None:
    path = appearance_image_path(media_dir, target, kind, extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read_appearance_image(
    media_dir: Path, target: AppearanceTarget, kind: AppearanceImageKind, extension: str
) -> bytes:
    return appearance_image_path(media_dir, target, kind, extension).read_bytes()


def delete_appearance_image(
    media_dir: Path, target: AppearanceTarget, kind: AppearanceImageKind, extension: str
) -> None:
    appearance_image_path(media_dir, target, kind, extension).unlink(missing_ok=True)
