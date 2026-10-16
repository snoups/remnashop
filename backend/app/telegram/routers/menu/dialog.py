from aiogram.enums import ParseMode
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.media import DynamicMedia
from aiogram_dialog.widgets.text import Format

from app.telegram.dialogs.keyboard import ConfigKeyboard
from app.telegram.routers.menu.catalog import register_menu_catalog
from app.telegram.routers.menu.getters import menu_getter
from app.telegram.states import MainMenu

register_menu_catalog()

main = Window(
    DynamicMedia("banner"),
    Format("{menu_text}"),
    ConfigKeyboard(window_key="menu.main"),
    parse_mode=ParseMode.HTML,
    state=MainMenu.MAIN,
    getter=menu_getter,
)

router = Dialog(main)
