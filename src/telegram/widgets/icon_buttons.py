from aiogram.types import InlineKeyboardButton
from aiogram_dialog.widgets.kbd import Button, SwitchInlineQueryChosenChatButton, SwitchTo, Url


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
