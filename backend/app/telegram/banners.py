from typing import Optional

from aiogram.enums import ContentType
from aiogram_dialog.api.entities import MediaAttachment

from app.core.config import AppConfig
from app.core.enums import Locale
from app.modules.banners import BannerRepository, banner_path


async def get_banner_media(
    banner_repository: BannerRepository,
    config: AppConfig,
    name: str,
    locale: Locale,
    default_locale: Locale,
) -> Optional[MediaAttachment]:
    banner = await banner_repository.find_for_display(name, locale, default_locale)
    if banner is None:
        return None

    path = banner_path(config.media_dir, banner.name, banner.locale, banner.extension)
    content_type = (
        ContentType.ANIMATION if banner.content_type == "image/gif" else ContentType.PHOTO
    )
    return MediaAttachment(type=content_type, path=path)
