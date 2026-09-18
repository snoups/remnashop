from aiogram.fsm.state import State
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.media import DynamicMedia
from aiogram_dialog.widgets.text import Format

from app.telegram.dialogs.keyboard import CustomConfigKeyboard
from app.telegram.dialogs.state_pool import custom_window_states
from app.telegram.routers.custom.getters import custom_window_getter


def _window(state: State) -> Window:
    return Window(
        DynamicMedia("banner", when="banner"),
        Format("{window_text}"),
        CustomConfigKeyboard(),
        state=state,
        getter=custom_window_getter,
    )


# One window per pooled state: which custom window a given state stands for is
# decided at render time from the config cache, so the dashboard can add and
# remove windows without the bot re-registering anything.
router = Dialog(*[_window(state) for state in custom_window_states()])
