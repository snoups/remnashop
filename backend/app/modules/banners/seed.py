from pathlib import Path
from typing import Final

from app.core.config import AppConfig
from app.core.constants import ASSETS_DIR, DEFAULT_BANNER_NAME
from app.core.enums import Locale
from app.modules.banners.dto import BannerDto, UploadBannerDto
from app.modules.banners.repository import BannerRepository
from app.modules.banners.storage import save_banner_file

_SOURCE: Final[Path] = ASSETS_DIR / "banners" / "default.png"
_CONTENT_TYPE: Final[str] = "image/png"
_EXTENSION: Final[str] = "png"


async def ensure_default_banner_seeded(
    banner_repository: BannerRepository, config: AppConfig, default_locale: Locale
) -> None:
    # Only the default locale: find_for_display already falls back to it, so one
    # row covers every language until an admin uploads a localized replacement.
    if await banner_repository.get(DEFAULT_BANNER_NAME, default_locale) is not None:
        return
    await restore_default_banner(banner_repository, config, default_locale)


async def restore_default_banner(
    banner_repository: BannerRepository, config: AppConfig, default_locale: Locale
) -> BannerDto:
    data = _SOURCE.read_bytes()
    banner = await banner_repository.upsert(
        UploadBannerDto(
            name=DEFAULT_BANNER_NAME,
            locale=default_locale,
            content_type=_CONTENT_TYPE,
            extension=_EXTENSION,
            size_bytes=len(data),
        )
    )
    save_banner_file(config.media_dir, DEFAULT_BANNER_NAME, default_locale, _EXTENSION, data)
    return banner


class DefaultBannerSeeder:
    def __init__(self, banner_repository: BannerRepository, config: AppConfig) -> None:
        self._banner_repository = banner_repository
        self._config = config

    async def ensure(self, locale: Locale) -> None:
        await ensure_default_banner_seeded(self._banner_repository, self._config, locale)
