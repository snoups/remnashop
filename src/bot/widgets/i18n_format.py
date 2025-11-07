from typing import Any, Optional, Union

from aiogram_dialog.api.internal import TextWidget
from aiogram_dialog.api.protocols import DialogManager
from aiogram_dialog.widgets.common import WhenCondition
from aiogram_dialog.widgets.text import Text
from dishka import AsyncContainer
from fluentogram import TranslatorRunner
from loguru import logger
from magic_filter import MagicFilter

from src.core.constants import CONTAINER_KEY
from src.core.i18n.translator import get_translated_kwargs
from src.core.utils.formatters import i18n_postprocess_text


def default_format_text(text: str, data: dict[str, Any]) -> str:
    return text.format_map(data)


class I18nFormat(Text):
    def __init__(
        self,
        key: str,
        when: Optional[WhenCondition] = None,
        /,
        **mapping: Union[TextWidget, MagicFilter, str, int, float, bool],
    ) -> None:
        super().__init__(when)
        self.key = key
        self.mapping = mapping

    async def _transform(
        self,
        data: dict[str, Any],
        dialog_manager: DialogManager,
    ) -> dict[str, Any]:
        mapped: dict[str, Any] = {}

        for key, transformer in self.mapping.items():
            if isinstance(transformer, TextWidget):
                mapped[key] = await transformer.render_text(data, dialog_manager)
            elif isinstance(transformer, MagicFilter):
                mapped[key] = transformer.resolve(data)
            else:
                mapped[key] = transformer

        logger.debug(f"Key '{self.key}' transformed mapping: {mapped}")
        return {**data, **mapped}

    async def _render_text(self, data: dict[str, Any], dialog_manager: DialogManager) -> str:
        container: AsyncContainer = dialog_manager.middleware_data[CONTAINER_KEY]
        i18n: TranslatorRunner = await container.get(TranslatorRunner)

        if self.mapping:
            data = await self._transform(data, dialog_manager)

        data = get_translated_kwargs(i18n, data)
        return i18n_postprocess_text(text=i18n.get(self.key.format_map(data), **data))
