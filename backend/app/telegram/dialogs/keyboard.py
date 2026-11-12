from collections.abc import Awaitable
from typing import Any, Optional, Union, cast

from aiogram.types import CallbackQuery, InlineKeyboardButton, KeyboardButton, WebAppInfo
from aiogram_dialog import StartMode
from aiogram_dialog.api.internal import RawKeyboard
from aiogram_dialog.api.protocols import DialogManager, DialogProtocol
from aiogram_dialog.widgets.kbd import Keyboard
from dishka import AsyncContainer
from dishka.integrations.aiogram_dialog import CONTAINER_NAME
from loguru import logger

from app.core.enums import ButtonLinkType
from app.modules.dialogs import catalog
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.state_pool import resolve_custom_window_key, resolve_state


async def _cache_from(manager: DialogManager) -> DialogConfigCache:
    container: AsyncContainer = manager.middleware_data[CONTAINER_NAME]
    return await container.get(DialogConfigCache)


class ConfigKeyboard(Keyboard):
    def __init__(self, window_key: Optional[str] = None, id: Optional[str] = None) -> None:
        # without a widget id Keyboard.callback_prefix() is falsy and
        # process_callback() never reaches _process_item_callback; one
        # ConfigKeyboard per window, so a fixed id is unique enough
        super().__init__(id=id or "cfgkb")
        self.window_key = window_key

    async def _resolve_window_key(self, manager: DialogManager) -> Optional[str]:
        return self.window_key

    async def _render_keyboard(self, data: dict[str, Any], manager: DialogManager) -> RawKeyboard:
        window_key = await self._resolve_window_key(manager)
        keyboard: RawKeyboard = []
        for row in data.get("buttons", []):
            rendered_row: list[Union[InlineKeyboardButton, KeyboardButton]] = []
            for button in row:
                if not button["text"]:
                    # Telegram rejects the whole keyboard over one empty button,
                    # so an unfilled label would take the window down
                    logger.warning(
                        f"Skipping button {button['id']} in window {window_key}: its label is empty"
                    )
                    continue
                # A plain emoji goes into the label: the icon field takes only a
                # custom emoji id, and is silently dropped if the bot's owner has
                # no Premium. With both stored the id wins; the glyph is there for
                # the dashboard, and adding it would show the emoji twice.
                icon_id = button.get("icon_custom_emoji_id")
                icon = button.get("icon")
                text = f"{icon} {button['text']}" if icon and not icon_id else button["text"]
                link_type = button["link_type"]
                if link_type in (ButtonLinkType.URL, ButtonLinkType.WEB_APP):
                    url = button["url_value"]
                    schemes = catalog.url_schemes_for(link_type)
                    if not url or not url.startswith(schemes) or url in schemes:
                        # Telegram rejects the whole keyboard over one bad URL, so
                        # a variable that resolved to nothing usable drops its own
                        # button instead of taking the window down.
                        logger.warning(
                            f"Skipping URL button {button['id']} in window {window_key}: "
                            f"unusable resolved url_value {url!r}"
                        )
                        continue
                    is_web_app = link_type == ButtonLinkType.WEB_APP
                    rendered_row.append(
                        InlineKeyboardButton(
                            text=text,
                            url=None if is_web_app else url,
                            web_app=WebAppInfo(url=url) if is_web_app else None,
                            icon_custom_emoji_id=icon_id,
                        )
                    )
                elif query := catalog.inline_query_for(button["action_key"]):
                    rendered_row.append(
                        InlineKeyboardButton(
                            text=text,
                            switch_inline_query=query,
                            style=button["style"],
                            icon_custom_emoji_id=icon_id,
                        )
                    )
                else:
                    rendered_row.append(
                        InlineKeyboardButton(
                            text=text,
                            callback_data=self._item_callback_data(str(button["id"])),
                            style=button["style"],
                            icon_custom_emoji_id=icon_id,
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
            logger.warning(f"Non-numeric dialog button id in window {self.window_key}: {item_id}")
            return False

        window_key = await self._resolve_window_key(manager)
        if window_key is None:
            logger.warning(f"Could not resolve the window behind button {button_id}")
            return False

        cache = await _cache_from(manager)
        button = await cache.get_button(window_key, button_id)
        if button is None:
            logger.warning(f"Unknown dialog button {button_id} in window {window_key}")
            return False

        if button.link_type == ButtonLinkType.ACTION:
            if button.action_key is None or not catalog.has_action_handler(button.action_key):
                logger.warning(
                    f"Unregistered action_key {button.action_key!r} on button {button_id} "
                    f"in window {window_key}"
                )
                return False
            handler = catalog.get_action(button.action_key)
            await cast(Awaitable[object], handler(callback, self, manager))
            return True

        if button.link_type == ButtonLinkType.NAVIGATE:
            if button.target_window_key is None:
                logger.warning(
                    f"NAVIGATE button {button_id} in window {window_key} has no target_window_key"
                )
                return False
            state = await resolve_state(button.target_window_key, cache)
            if state is None:
                logger.warning(
                    f"Could not resolve state for target window {button.target_window_key} "
                    f"(from button {button_id} in window {window_key})"
                )
                return False
            if state.group == manager.current_context().state.group:
                await manager.switch_to(state=state)
            else:
                # switch_to() refuses to cross state groups, and a configured
                # jump routinely does (seed windows and custom ones live in
                # different groups). RESET_STACK keeps hopping between them from
                # growing the stack a level per click.
                await manager.start(state=state, mode=StartMode.RESET_STACK)
            return True

        logger.warning(
            f"Button {button_id} in window {window_key} has unhandled link_type {button.link_type}"
        )
        return False


class CustomConfigKeyboard(ConfigKeyboard):
    """The keyboard of a custom window, which has no window key of its own at
    import time: every custom window renders through a pooled state, and which
    window that state currently stands for is only known from the config cache."""

    async def _resolve_window_key(self, manager: DialogManager) -> Optional[str]:
        cache = await _cache_from(manager)
        return await resolve_custom_window_key(manager.current_context().state, cache)
