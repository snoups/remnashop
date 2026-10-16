from aiogram.enums import ParseMode
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Button, ListGroup
from aiogram_dialog.widgets.media import DynamicMedia
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from app.telegram.dialogs.keyboard import ConfigKeyboard
from app.telegram.routers.subscriptions.catalog import register_subscriptions_catalog
from app.telegram.routers.subscriptions.getters import (
    device_confirm_delete_all_getter,
    device_confirm_delete_getter,
    device_confirm_reissue_getter,
    devices_getter,
    subscription_card_getter,
    subscriptions_list_getter,
)
from app.telegram.routers.subscriptions.handlers import (
    on_device_delete_request,
    on_subscription_selected,
)
from app.telegram.states import Subscriptions

register_subscriptions_catalog()

subscriptions_list = Window(
    DynamicMedia("banner", when="banner"),
    Format("{window_text}"),
    ListGroup(
        Button(text=Format("{item[label]}"), id="subscription", on_click=on_subscription_selected),
        id="subscriptions",
        item_id_getter=lambda item: item["id"],
        items="subscriptions",
    ),
    ConfigKeyboard(window_key="subscriptions.list"),
    parse_mode=ParseMode.HTML,
    state=Subscriptions.LIST,
    getter=subscriptions_list_getter,
)

subscription_card = Window(
    DynamicMedia("banner", when="banner"),
    Format("{window_text}"),
    ConfigKeyboard(window_key="subscriptions.card"),
    parse_mode=ParseMode.HTML,
    state=Subscriptions.CARD,
    getter=subscription_card_getter,
)

devices = Window(
    DynamicMedia("banner"),
    Format("{devices_header}"),
    Button(text=Format("{empty_text}"), id="devices_empty", when=~F["has_devices"]),
    ListGroup(
        Button(text=Format("{item[label]}"), id="device_item", on_click=on_device_delete_request),
        id="devices_list",
        item_id_getter=lambda item: item["index"],
        items="devices",
        when=F["has_devices"],
    ),
    ConfigKeyboard(window_key="menu.devices"),
    parse_mode=ParseMode.HTML,
    state=Subscriptions.DEVICES,
    getter=devices_getter,
)

device_confirm_delete = Window(
    DynamicMedia("banner"),
    Format("{confirm_message}"),
    ConfigKeyboard(window_key="menu.device_confirm_delete"),
    parse_mode=ParseMode.HTML,
    state=Subscriptions.DEVICE_CONFIRM_DELETE,
    getter=device_confirm_delete_getter,
)

device_confirm_delete_all = Window(
    DynamicMedia("banner"),
    Format("{confirm_message}"),
    ConfigKeyboard(window_key="menu.device_confirm_delete_all"),
    parse_mode=ParseMode.HTML,
    state=Subscriptions.DEVICE_CONFIRM_DELETE_ALL,
    getter=device_confirm_delete_all_getter,
)

device_confirm_reissue = Window(
    DynamicMedia("banner"),
    Format("{confirm_message}"),
    ConfigKeyboard(window_key="menu.device_confirm_reissue"),
    parse_mode=ParseMode.HTML,
    state=Subscriptions.DEVICE_CONFIRM_REISSUE,
    getter=device_confirm_reissue_getter,
)

router = Dialog(
    subscriptions_list,
    subscription_card,
    devices,
    device_confirm_delete,
    device_confirm_delete_all,
    device_confirm_reissue,
)
