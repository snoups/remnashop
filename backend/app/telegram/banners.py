from typing import Optional

from aiogram.enums import ContentType
from aiogram_dialog.api.entities import MediaAttachment

from app.core.config import AppConfig
from app.modules.banners import BannerKeyDto, GetBannerForDisplayUseCase, banner_path
from app.modules.users import UserDto


async def get_banner_media(
    get_banner: GetBannerForDisplayUseCase, config: AppConfig, user: UserDto, name: str
) -> Optional[MediaAttachment]:
    banner = await get_banner(user, BannerKeyDto(name=name, locale=user.language))
    if banner is None:
        return None

    path = banner_path(config.media_dir, banner.name, banner.locale, banner.extension)
    content_type = (
        ContentType.ANIMATION if banner.content_type == "image/gif" else ContentType.PHOTO
    )
    return MediaAttachment(type=content_type, path=path)
