import logging
from typing import cast

from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.common import Whenable
from aiogram_dialog.widgets.media import StaticMedia

from app.core.config import DEFAULT_BANNERS_DIR, AppConfig
from app.core.constants import CONFIG_KEY, MIDDLEWARE_DATA_KEY
from app.core.enums import BannerFormat, BannerName

logger = logging.getLogger(__name__)  # FIX: not working in this file, but works in others


class Banner(StaticMedia):
    def __init__(self, name: BannerName) -> None:
        path = None
        content_type = None

        for format in BannerFormat:
            candidate_path = DEFAULT_BANNERS_DIR / f"{name.value}.{format.value}"
            if candidate_path.exists():
                path = candidate_path
                content_type = format.content_type
                break

        if path is None:
            logger.warning(f"Banner file for '{name.value}' not found. Using default")
            path = DEFAULT_BANNERS_DIR / f"{BannerName.DEFAULT.value}.{BannerFormat.JPG.value}"
            content_type = BannerFormat.JPG.content_type

        if not path.exists():
            raise FileNotFoundError(f"Default banner file not found: {path}")

        def predicate(data: dict, widget: Whenable, dialog_manager: DialogManager) -> bool:
            middleware_data: dict = data.get(MIDDLEWARE_DATA_KEY) or {}
            config = cast(AppConfig, middleware_data.get(CONFIG_KEY))

            if config is None:
                logger.warning("Missing AppConfig in middleware data.")
                return False

            return config.bot.use_banners

        super().__init__(path=path, type=content_type, when=predicate)
