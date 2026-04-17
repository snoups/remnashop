import functools
from pathlib import Path
from typing import Any, Optional

from aiogram.types import ContentType
from aiogram_dialog import DialogManager
from aiogram_dialog.api.entities import MediaAttachment
from aiogram_dialog.widgets.common import Whenable
from aiogram_dialog.widgets.media import StaticMedia
from loguru import logger

from src.application.dto import UserDto
from src.core.config import AppConfig
from src.core.constants import CONFIG_KEY, USER_KEY
from src.core.enums import BannerFormat, BannerName, Locale


@functools.lru_cache(maxsize=64)
def get_banner(
    banners_dir: Path,
    name: BannerName,
    locale: Locale,
    default_locale: Locale,
) -> tuple[Path, ContentType]:
    search_targets = [
        (banners_dir / locale, name),
        (banners_dir / locale, BannerName.DEFAULT),
        (banners_dir / default_locale, name),
        (banners_dir / default_locale, BannerName.DEFAULT),
        (banners_dir, BannerName.DEFAULT),
    ]

    for directory, banner_name in search_targets:
        if not directory.exists():
            continue

        for banner_format in BannerFormat:
            candidate = directory / f"{banner_name}.{banner_format}"
            if candidate.exists():
                logger.debug(f"Banner '{banner_name}' found at '{candidate}'")
                return candidate, banner_format.content_type

    logger.error(f"Banner '{name}' not found in any location including global default")
    raise FileNotFoundError(f"Banner '{name}' or global default not found")


class Banner(StaticMedia):
    def __init__(self, name: BannerName) -> None:
        self.banner_name = name
        super().__init__(path="path", url=None, type=ContentType.UNKNOWN, when=self._is_use_banners)

    def _is_use_banners(
        self,
        data: dict[str, Any],
        widget: Whenable,
        dialog_manager: DialogManager,
    ) -> bool:
        config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]
        return config.bot.use_banners

    async def _render_media(self, data: dict, manager: DialogManager) -> Optional[MediaAttachment]:
        user: UserDto = manager.middleware_data[USER_KEY]
        config: AppConfig = manager.middleware_data[CONFIG_KEY]

        try:
            banner_path, banner_content_type = get_banner(
                banners_dir=config.banners_dir,
                name=self.banner_name,
                locale=user.language,
                default_locale=config.default_locale,
            )
        except FileNotFoundError:
            logger.critical(f"Failed to render banner '{self.banner_name}' because file is missing")
            return None

        return MediaAttachment(
            type=banner_content_type,
            path=banner_path,
            use_pipe=self.use_pipe,
            **self.media_params,
        )
