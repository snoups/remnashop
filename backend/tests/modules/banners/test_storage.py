from pathlib import Path

from app.core.enums import BannerName, Locale
from app.modules.banners.storage import (
    banner_path,
    delete_banner_file,
    read_banner_file,
    save_banner_file,
)


def test_banner_path_is_deterministic(tmp_path: Path) -> None:
    path = banner_path(tmp_path, BannerName.MENU, Locale.RU, "jpg")
    assert path == tmp_path / "banners" / "menu_ru.jpg"


def test_save_then_read_roundtrips(tmp_path: Path) -> None:
    save_banner_file(tmp_path, BannerName.MENU, Locale.RU, "jpg", b"fake-image-bytes")

    data = read_banner_file(tmp_path, BannerName.MENU, Locale.RU, "jpg")
    assert data == b"fake-image-bytes"


def test_save_creates_banners_subdirectory(tmp_path: Path) -> None:
    save_banner_file(tmp_path, BannerName.MENU, Locale.RU, "jpg", b"x")
    assert (tmp_path / "banners").is_dir()


def test_save_overwrites_existing_file(tmp_path: Path) -> None:
    save_banner_file(tmp_path, BannerName.MENU, Locale.RU, "jpg", b"first")
    save_banner_file(tmp_path, BannerName.MENU, Locale.RU, "jpg", b"second")

    assert read_banner_file(tmp_path, BannerName.MENU, Locale.RU, "jpg") == b"second"


def test_delete_removes_file(tmp_path: Path) -> None:
    save_banner_file(tmp_path, BannerName.MENU, Locale.RU, "jpg", b"x")
    delete_banner_file(tmp_path, BannerName.MENU, Locale.RU, "jpg")

    assert not banner_path(tmp_path, BannerName.MENU, Locale.RU, "jpg").exists()


def test_delete_missing_file_does_not_raise(tmp_path: Path) -> None:
    delete_banner_file(tmp_path, BannerName.MENU, Locale.RU, "jpg")
