import logging
from collections.abc import Awaitable
from typing import Any, Optional, Union, cast

from aiogram.types import CallbackQuery, InlineKeyboardButton, KeyboardButton
from aiogram_dialog.api.internal import RawKeyboard
from aiogram_dialog.api.protocols import DialogManager, DialogProtocol
from aiogram_dialog.widgets.kbd import Keyboard
from dishka import AsyncContainer
from dishka.integrations.aiogram_dialog import CONTAINER_NAME

from app.core.enums import ButtonLinkType
from app.modules.dialogs import catalog
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.state_pool import resolve_state

logger = logging.getLogger(__name__)


class ConfigKeyboard(Keyboard):
    def __init__(self, window_key: str, id: Optional[str] = None) -> None:
        # Keyboard.callback_prefix() is falsy without a widget id, so
        # process_callback() never reaches _process_item_callback -- every
        # window has exactly one ConfigKeyboard, so a fixed id only needs to
        # be unique within the window, not globally.
        super().__init__(id=id or "cfgkb")
        self.window_key = window_key

    async def _render_keyboard(self, data: dict[str, Any], manager: DialogManager) -> RawKeyboard:
        keyboard: RawKeyboard = []
        for row in data.get("buttons", []):
            rendered_row: list[Union[InlineKeyboardButton, KeyboardButton]] = []
            for button in row:
                if button["link_type"] == ButtonLinkType.URL:
                    if not button["url_value"]:
                        logger.warning(
                            "Skipping URL button %s in window %s: empty resolved url_value",
                            button["id"],
                            self.window_key,
                        )
                        continue
                    rendered_row.append(
                        InlineKeyboardButton(text=button["text"], url=button["url_value"])
                    )
                else:
                    rendered_row.append(
                        InlineKeyboardButton(
                            text=button["text"],
                            callback_data=self._item_callback_data(str(button["id"])),
                            style=button["style"],
                            icon_custom_emoji_id=button["icon_custom_emoji_id"],
                        )
                    )
            if rendered_row:
                keyboard.append(rendered_row)
        return keyboard

    async def _process_item_callback(
        self,
        callback: CallbackQuery,
        item_id: str,
        dialog: DialogProtocol,
        manager: DialogManager,
    ) -> bool:
        try:
            button_id = int(item_id)
        except ValueError:
            logger.warning(
                "Non-numeric dialog button id in window %s: %s", self.window_key, item_id
            )
            return False

        container: AsyncContainer = manager.middleware_data[CONTAINER_NAME]
        cache = await container.get(DialogConfigCache)
        button = await cache.get_button(self.window_key, button_id)
        if button is None:
            logger.warning("Unknown dialog button %s in window %s", button_id, self.window_key)
            return False

        if button.link_type == ButtonLinkType.ACTION:
            if button.action_key is None or not catalog.has_action_handler(button.action_key):
                logger.warning(
                    "Unregistered action_key %r on button %s in window %s",
                    button.action_key,
                    button_id,
                    self.window_key,
                )
                return False
            handler = catalog.get_action(button.action_key)
            await cast(Awaitable[object], handler(callback, self, manager))
            return True

        if button.link_type == ButtonLinkType.NAVIGATE:
            if button.target_window_key is None:
                logger.warning(
                    "NAVIGATE button %s in window %s has no target_window_key",
                    button_id,
                    self.window_key,
                )
                return False
            state = await resolve_state(button.target_window_key, cache)
            if state is None:
                logger.warning(
                    "Could not resolve state for target window %s (from button %s in window %s)",
                    button.target_window_key,
                    button_id,
                    self.window_key,
                )
                return False
            await manager.switch_to(state=state)
            return True

        logger.warning(
            "Button %s in window %s has unhandled link_type %s",
            button_id,
            self.window_key,
            button.link_type,
        )
        return False
