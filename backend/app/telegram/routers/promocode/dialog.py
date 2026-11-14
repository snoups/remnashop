from aiogram.enums import ParseMode
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Cancel, ListGroup, Row, SwitchTo
from aiogram_dialog.widgets.text import Format

from app.telegram.dialogs.rendering import LabelIcon
from app.telegram.routers.promocode.getters import (
    promocode_confirm_getter,
    promocode_input_getter,
    promocode_target_getter,
)
from app.telegram.routers.promocode.handlers import (
    on_promocode_confirm,
    on_promocode_input,
    on_target_subscription_selected,
)
from app.telegram.states import Promocode

promocode_input = Window(
    Format("{input_message}"),
    MessageInput(on_promocode_input),
    Row(
        Cancel(Format("{cancel_text}"), style=LabelIcon("cancel_text"), id="cancel"),
    ),
    parse_mode=ParseMode.HTML,
    state=Promocode.INPUT,
    getter=promocode_input_getter,
)

promocode_target = Window(
    Format("{target_message}"),
    ListGroup(
        Button(
            text=Format("{item[label]}"),
            id="target_item",
            on_click=on_target_subscription_selected,
        ),
        id="target_list",
        item_id_getter=lambda item: item["id"],
        items="subscriptions",
    ),
    Row(
        SwitchTo(
            text=Format("{cancel_text}"),
            style=LabelIcon("cancel_text"),
            id="cancel",
            state=Promocode.INPUT,
        ),
    ),
    parse_mode=ParseMode.HTML,
    state=Promocode.TARGET,
    getter=promocode_target_getter,
)

promocode_confirm = Window(
    Format("{confirm_message}"),
    Format("{will_replace_message}"),
    Row(
        Button(
            text=Format("{confirm_text}"),
            style=LabelIcon("confirm_text"),
            id="confirm",
            on_click=on_promocode_confirm,
        ),
        SwitchTo(
            text=Format("{cancel_text}"),
            style=LabelIcon("cancel_text"),
            id="cancel",
            state=Promocode.INPUT,
        ),
    ),
    parse_mode=ParseMode.HTML,
    state=Promocode.CONFIRM,
    getter=promocode_confirm_getter,
)

router = Dialog(promocode_input, promocode_target, promocode_confirm)
