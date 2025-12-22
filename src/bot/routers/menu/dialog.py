from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Button, Row
from aiogram_dialog.widgets.text import Format

from src.bot.states import MainMenu
from src.bot.widgets import IgnoreUpdate

from .getters import menu_getter

menu = Window(
    Format("msg-main-menu"),
    Row(
        Button(
            text=Format("btn-test"),
            id="trial",
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.MAIN,
    getter=menu_getter,
)

router = Dialog(menu)
