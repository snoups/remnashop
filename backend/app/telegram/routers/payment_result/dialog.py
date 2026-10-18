from aiogram.enums import ParseMode
from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.kbd import Button, Start
from aiogram_dialog.widgets.text import Format

from app.telegram.routers.payment_result.getters import (
    canceled_getter,
    failed_getter,
    success_getter,
)
from app.telegram.routers.payment_result.handlers import on_open_subscription, on_retry
from app.telegram.states import MainMenu, PaymentResult


def _menu() -> Start:
    return Start(Format("{menu_text}"), id="menu", state=MainMenu.MAIN, mode=StartMode.RESET_STACK)


success = Window(
    Format("{window_text}"),
    Button(
        Format("{subscription_text}"),
        id="subscription",
        on_click=on_open_subscription,
        when="has_subscription",
    ),
    _menu(),
    parse_mode=ParseMode.HTML,
    state=PaymentResult.SUCCESS,
    getter=success_getter,
)

failed = Window(
    Format("{window_text}"),
    _menu(),
    parse_mode=ParseMode.HTML,
    state=PaymentResult.FAILED,
    getter=failed_getter,
)

canceled = Window(
    Format("{window_text}"),
    Button(Format("{retry_text}"), id="retry", on_click=on_retry),
    _menu(),
    parse_mode=ParseMode.HTML,
    state=PaymentResult.CANCELED,
    getter=canceled_getter,
)

router = Dialog(success, failed, canceled)
