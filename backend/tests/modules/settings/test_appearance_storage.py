from pathlib import Path

from app.core.enums import AppearanceImageKind
from app.modules.settings.appearance_storage import (
    appearance_image_path,
    delete_appearance_image,
    read_appearance_image,
    save_appearance_image,
)


def test_appearance_image_path_is_deterministic(tmp_path: Path) -> None:
    path = appearance_image_path(tmp_path, AppearanceImageKind.LOGO, "png")
    assert path == tmp_path / "appearance" / "logo.png"


def test_save_then_read_roundtrips(tmp_path: Path) -> None:
    save_appearance_image(tmp_path, AppearanceImageKind.LOGO, "png", b"fake-image-bytes")

    data = read_appearance_image(tmp_path, AppearanceImageKind.LOGO, "png")
    assert data == b"fake-image-bytes"


def test_save_creates_appearance_subdirectory(tmp_path: Path) -> None:
    save_appearance_image(tmp_path, AppearanceImageKind.FAVICON, "png", b"x")
    assert (tmp_path / "appearance").is_dir()


def test_save_overwrites_existing_file(tmp_path: Path) -> None:
    save_appearance_image(tmp_path, AppearanceImageKind.LOGO, "png", b"first")
    save_appearance_image(tmp_path, AppearanceImageKind.LOGO, "png", b"second")

    assert read_appearance_image(tmp_path, AppearanceImageKind.LOGO, "png") == b"second"


def test_delete_removes_file(tmp_path: Path) -> None:
    save_appearance_image(tmp_path, AppearanceImageKind.LOGO, "png", b"x")
    delete_appearance_image(tmp_path, AppearanceImageKind.LOGO, "png")

    assert not appearance_image_path(tmp_path, AppearanceImageKind.LOGO, "png").exists()


def test_delete_missing_file_does_not_raise(tmp_path: Path) -> None:
    delete_appearance_image(tmp_path, AppearanceImageKind.LOGO, "png")
