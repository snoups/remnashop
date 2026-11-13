from typing import Any, Awaitable, Callable, Optional

from aiogram.enums import ContentType
from aiogram_dialog import DialogManager
from aiogram_dialog.api.entities import MediaAttachment
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from app.core.config import AppConfig
from app.core.constants import USER_KEY
from app.modules.banners import BannerKeyDto, GetBannerForDisplayUseCase, banner_path
from app.modules.users import UserDto
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.rendering import banner_within_caption

WindowGetter = Callable[..., Awaitable[dict[str, Any]]]


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


async def window_banner(
    key: str,
    dialog_config_cache: DialogConfigCache,
    get_banner: GetBannerForDisplayUseCase,
    config: AppConfig,
    user: UserDto,
) -> Optional[MediaAttachment]:
    """The banner the dashboard set on the catalog window `key`, if any."""
    window = await dialog_config_cache.get_window(key)
    if not window.banner_name:
        return None
    return await get_banner_media(get_banner, config, user, window.banner_name)


def with_window_banner(key: str, getter: WindowGetter) -> WindowGetter:
    """A code-defined window's getter plus the banner of the catalog window `key`,
    dropped when its `window_text` is too long for a caption."""

    @inject
    async def wrapped(
        dialog_manager: DialogManager,
        config: FromDishka[AppConfig],
        get_banner: FromDishka[GetBannerForDisplayUseCase],
        dialog_config_cache: FromDishka[DialogConfigCache],
        **kwargs: Any,
    ) -> dict[str, Any]:
        data = await getter(dialog_manager=dialog_manager, **kwargs)
        user: UserDto = dialog_manager.middleware_data[USER_KEY]
        banner = await window_banner(key, dialog_config_cache, get_banner, config, user)
        data["banner"] = banner_within_caption(banner, data["window_text"])
        return data

    return wrapped
