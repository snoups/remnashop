from typing import Optional

from aiogram.enums import ContentType
from loguru import logger

from app.core.config import AppConfig
from app.core.enums import BannerName, Locale
from app.modules.banners import BannerRepository, read_banner_file


async def get_banner(
    banner_repository: BannerRepository,
    config: AppConfig,
    name: BannerName,
    locale: Locale,
    default_locale: Locale,
) -> Optional[tuple[bytes, ContentType]]:
    banner = await banner_repository.find_for_display(name, locale, default_locale)
    if banner is None:
        return None

    try:
        data = read_banner_file(config.media_dir, banner.name, banner.locale, banner.extension)
    except FileNotFoundError:
        logger.warning(f"Banner file for '{banner.name}/{banner.locale}' not found on disk")
        return None

    content_type = (
        ContentType.ANIMATION if banner.content_type == "image/gif" else ContentType.PHOTO
    )
    return data, content_type
