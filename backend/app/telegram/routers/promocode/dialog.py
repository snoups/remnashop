from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, ListGroup, Row, Start, SwitchTo
from aiogram_dialog.widgets.media import DynamicMedia
from aiogram_dialog.widgets.text import Format

from app.telegram.routers.promocode.getters import (
    promocode_confirm_getter,
    promocode_input_getter,
    promocode_target_getter,
    subscription_main_getter,
)
from app.telegram.routers.promocode.handlers import (
    on_promocode_confirm,
    on_promocode_input,
    on_target_subscription_selected,
)
from app.telegram.states import MainMenu, Subscription

subscription_main = Window(
    DynamicMedia("banner"),
    Format("{message}"),
    Row(
        SwitchTo(text=Format("{promocode_text}"), id="promocode", state=Subscription.PROMOCODE),
    ),
    Row(
        Start(
            text=Format("{back_text}"),
            id="back_to_menu",
            state=MainMenu.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    state=Subscription.MAIN,
    getter=subscription_main_getter,
)

promocode_input = Window(
    Format("{input_message}"),
    MessageInput(on_promocode_input),
    Row(
        SwitchTo(text=Format("{cancel_text}"), id="cancel", state=Subscription.MAIN),
    ),
    state=Subscription.PROMOCODE,
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
        SwitchTo(text=Format("{cancel_text}"), id="cancel", state=Subscription.MAIN),
    ),
    state=Subscription.PROMOCODE_TARGET,
    getter=promocode_target_getter,
)

promocode_confirm = Window(
    Format("{confirm_message}"),
    Format("{will_replace_message}"),
    Row(
        Button(text=Format("{confirm_text}"), id="confirm", on_click=on_promocode_confirm),
        SwitchTo(text=Format("{cancel_text}"), id="cancel", state=Subscription.PROMOCODE),
    ),
    state=Subscription.PROMOCODE_CONFIRM,
    getter=promocode_confirm_getter,
)

router = Dialog(subscription_main, promocode_input, promocode_target, promocode_confirm)
