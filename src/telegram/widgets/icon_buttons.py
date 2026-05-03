from collections.abc import Callable
from typing import Any

from aiogram.types import InlineKeyboardButton
from aiogram_dialog.widgets.kbd import Button, Select, SwitchInlineQueryChosenChatButton, SwitchTo, Url


class IconButton(Button):
    def __init__(self, *args, icon_custom_emoji_id: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon_custom_emoji_id = icon_custom_emoji_id

    async def _render_keyboard(self, data, manager):
        keyboard = await super()._render_keyboard(data, manager)

        for row in keyboard:
            for btn in row:
                if isinstance(btn, InlineKeyboardButton):
                    btn.icon_custom_emoji_id = self.icon_custom_emoji_id

        return keyboard


class IconSelect(Select):
    def __init__(
        self,
        *args: Any,
        icon_custom_emoji_id_getter: Callable[[Any], str | None],
        icon_items_key: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.icon_custom_emoji_id_getter = icon_custom_emoji_id_getter
        self.icon_items_key = icon_items_key

    async def _render_keyboard(self, data, manager):
        keyboard = await super()._render_keyboard(data, manager)
        items = data.get(self.icon_items_key, [])
        buttons = [
            button
            for row in keyboard
            for button in row
            if isinstance(button, InlineKeyboardButton)
        ]

        for button, item in zip(buttons, items):
            icon_custom_emoji_id = self.icon_custom_emoji_id_getter(item)
            if icon_custom_emoji_id:
                button.icon_custom_emoji_id = icon_custom_emoji_id

        return keyboard


class IconSwitchTo(SwitchTo):
    def __init__(self, *args, icon_custom_emoji_id: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon_custom_emoji_id = icon_custom_emoji_id

    async def _render_keyboard(self, data, manager):
        keyboard = await super()._render_keyboard(data, manager)

        for row in keyboard:
            for btn in row:
                if isinstance(btn, InlineKeyboardButton):
                    btn.icon_custom_emoji_id = self.icon_custom_emoji_id

        return keyboard


class IconSwitchInlineQueryChosenChatButton(SwitchInlineQueryChosenChatButton):
    def __init__(self, *args, icon_custom_emoji_id: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon_custom_emoji_id = icon_custom_emoji_id

    async def _render_keyboard(self, data, manager):
        keyboard = await super()._render_keyboard(data, manager)

        for row in keyboard:
            for btn in row:
                if isinstance(btn, InlineKeyboardButton):
                    btn.icon_custom_emoji_id = self.icon_custom_emoji_id

        return keyboard


class IconUrl(Url):
    def __init__(self, *args, icon_custom_emoji_id: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon_custom_emoji_id = icon_custom_emoji_id

    async def _render_keyboard(self, data, manager):
        keyboard = await super()._render_keyboard(data, manager)

        for row in keyboard:
            for btn in row:
                if isinstance(btn, InlineKeyboardButton):
                    btn.icon_custom_emoji_id = self.icon_custom_emoji_id

        return keyboard
