import functools
from pathlib import Path
from typing import Any, Optional

from aiogram.types import ContentType
from aiogram_dialog import DialogManager
from aiogram_dialog.api.entities import MediaAttachment
from aiogram_dialog.widgets.common import Whenable
from aiogram_dialog.widgets.media import StaticMedia
from loguru import logger

from src.core.config import AppConfig
from src.core.constants import CONFIG_KEY, USER_KEY
from src.core.enums import BannerFormat, BannerName, Locale
from src.infrastructure.database.models.dto import UserDto


@functools.lru_cache(maxsize=None)
def get_banner(
    banners_dir: Path,
    name: BannerName,
    locale: Locale,
    default_locale: Locale,
) -> tuple[Path, ContentType]:
    for current_locale in [locale, default_locale]:
        path_locale = banners_dir / current_locale

        if not path_locale.exists():
            continue

        for format in BannerFormat:
            path = path_locale / f"{name}.{format}"

            if not path.exists():
                continue

            content_type = format.content_type
            logger.debug(f"Found banner '{name}' in locale '{current_locale}': '{path}'")
            return path, content_type

    logger.warning(f"Banner '{name}' not found in locales '{locale}' or '{default_locale}'")
    path = banners_dir / f"{BannerName.DEFAULT}.{BannerFormat.JPG}"
    content_type = BannerFormat.JPG.content_type

    if not path.exists():
        raise FileNotFoundError(f"Default banner not found: '{path}'")

    return path, content_type


class Banner(StaticMedia):
    def __init__(self, name: BannerName) -> None:
        self.banner_name = name

        def _is_use_banners(
            data: dict[str, Any],
            widget: Whenable,
            dialog_manager: DialogManager,
        ) -> bool:
            config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]
            return config.bot.use_banners

        super().__init__(path="path", url=None, type=ContentType.UNKNOWN, when=_is_use_banners)

    async def _render_media(self, data: dict, manager: DialogManager) -> Optional[MediaAttachment]:
        user: UserDto = manager.middleware_data[USER_KEY]
        config: AppConfig = manager.middleware_data[CONFIG_KEY]

        banner_path, banner_content_type = get_banner(
            banners_dir=config.banners_dir,
            name=self.banner_name,
            locale=user.language,
            default_locale=config.default_locale,
        )

        return MediaAttachment(
            type=banner_content_type,
            url=None,
            path=banner_path,
            use_pipe=self.use_pipe,
            **self.media_params,
        )
