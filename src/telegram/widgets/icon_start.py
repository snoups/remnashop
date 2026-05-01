# src/telegram/widgets/icon_start.py

from aiogram.types import InlineKeyboardButton
from aiogram_dialog.widgets.kbd import Start


class IconStart(Start):
    def __init__(self, *args, icon_custom_emoji_id: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon_custom_emoji_id = icon_custom_emoji_id

    async def _render_keyboard(self, data, manager):
        keyboard = await super()._render_keyboard(data, manager)

        for row in keyboard:
            for button in row:
                if isinstance(button, InlineKeyboardButton):
                    button.icon_custom_emoji_id = self.icon_custom_emoji_id

        return keyboard