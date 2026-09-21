import re
from pathlib import Path
from typing import Final

from app.core.constants import BANNER_NAME_PATTERN
from app.core.enums import Locale

_NAME_RE: Final[re.Pattern[str]] = re.compile(BANNER_NAME_PATTERN)


def validate_banner_name(name: str) -> str:
    if _NAME_RE.match(name) is None or ".." in name:
        raise ValueError(f"Invalid banner name: {name!r}")
    return name


def banner_path(media_dir: Path, name: str, locale: Locale, extension: str) -> Path:
    return media_dir / "banners" / f"{validate_banner_name(name)}_{locale}.{extension}"


def save_banner_file(
    media_dir: Path, name: str, locale: Locale, extension: str, data: bytes
) -> None:
    path = banner_path(media_dir, name, locale, extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read_banner_file(media_dir: Path, name: str, locale: Locale, extension: str) -> bytes:
    return banner_path(media_dir, name, locale, extension).read_bytes()


def delete_banner_file(media_dir: Path, name: str, locale: Locale, extension: str) -> None:
    banner_path(media_dir, name, locale, extension).unlink(missing_ok=True)
