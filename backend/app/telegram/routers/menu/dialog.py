from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Button, ListGroup, Row, Start
from aiogram_dialog.widgets.media import DynamicMedia
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from app.telegram.dialogs.catalog_menu import register_menu_catalog
from app.telegram.dialogs.keyboard import ConfigKeyboard
from app.telegram.routers.menu.getters import (
    device_confirm_delete_all_getter,
    device_confirm_delete_getter,
    device_confirm_reissue_getter,
    devices_getter,
    menu_getter,
)
from app.telegram.routers.menu.handlers import on_device_delete_request
from app.telegram.states import MainMenu, Subscription

register_menu_catalog()

main = Window(
    DynamicMedia("banner"),
    Format("{menu_text}"),
    ConfigKeyboard(window_key="menu.main"),
    Row(
        Start(
            text=Format("{subscription_text}"),
            id="subscription",
            state=Subscription.MAIN,
        ),
    ),
    state=MainMenu.MAIN,
    getter=menu_getter,
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
    state=MainMenu.DEVICES,
    getter=devices_getter,
)

device_confirm_delete = Window(
    DynamicMedia("banner"),
    Format("{confirm_message}"),
    ConfigKeyboard(window_key="menu.device_confirm_delete"),
    state=MainMenu.DEVICE_CONFIRM_DELETE,
    getter=device_confirm_delete_getter,
)

device_confirm_delete_all = Window(
    DynamicMedia("banner"),
    Format("{confirm_message}"),
    ConfigKeyboard(window_key="menu.device_confirm_delete_all"),
    state=MainMenu.DEVICE_CONFIRM_DELETE_ALL,
    getter=device_confirm_delete_all_getter,
)

device_confirm_reissue = Window(
    DynamicMedia("banner"),
    Format("{confirm_message}"),
    ConfigKeyboard(window_key="menu.device_confirm_reissue"),
    state=MainMenu.DEVICE_CONFIRM_REISSUE,
    getter=device_confirm_reissue_getter,
)

router = Dialog(
    main, devices, device_confirm_delete, device_confirm_delete_all, device_confirm_reissue
)
