from pathlib import Path

from app.core.enums import BannerName, Locale


def banner_path(media_dir: Path, name: BannerName, locale: Locale, extension: str) -> Path:
    return media_dir / "banners" / f"{name}_{locale}.{extension}"


def save_banner_file(
    media_dir: Path, name: BannerName, locale: Locale, extension: str, data: bytes
) -> None:
    path = banner_path(media_dir, name, locale, extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read_banner_file(media_dir: Path, name: BannerName, locale: Locale, extension: str) -> bytes:
    return banner_path(media_dir, name, locale, extension).read_bytes()


def delete_banner_file(media_dir: Path, name: BannerName, locale: Locale, extension: str) -> None:
    banner_path(media_dir, name, locale, extension).unlink(missing_ok=True)
