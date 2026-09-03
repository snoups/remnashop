from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Button, ListGroup, Row, Start, SwitchTo, Url
from aiogram_dialog.widgets.media import DynamicMedia
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from app.telegram.routers.menu.getters import (
    device_confirm_delete_all_getter,
    device_confirm_delete_getter,
    device_confirm_reissue_getter,
    devices_getter,
    menu_getter,
)
from app.telegram.routers.menu.handlers import (
    on_device_delete_all_confirm,
    on_device_delete_confirm,
    on_device_delete_request,
    on_get_trial,
    on_reissue_subscription_confirm,
)
from app.telegram.states import MainMenu, Subscription

main = Window(
    DynamicMedia("banner"),
    Format("{menu_text}"),
    Row(
        Url(
            text=Format("{connect_text}"),
            id="connect",
            url=Format("{connect_url}"),
            when=F["connectable"] & F["connect_url"],
        ),
    ),
    Row(
        Button(
            text=Format("{trial_text}"),
            id="trial",
            on_click=on_get_trial,
            when=F["trial_available"],
        ),
    ),
    Row(
        SwitchTo(
            text=Format("{devices_text}"),
            id="devices",
            state=MainMenu.DEVICES,
            when=F["has_device_limit"],
        ),
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
    Row(
        SwitchTo(
            text=Format("{delete_all_text}"),
            id="delete_all",
            state=MainMenu.DEVICE_CONFIRM_DELETE_ALL,
            when=F["has_devices"],
        ),
    ),
    Row(
        SwitchTo(
            text=Format("{reissue_text}"), id="reissue", state=MainMenu.DEVICE_CONFIRM_REISSUE
        ),
    ),
    Row(
        SwitchTo(text=Format("{back_text}"), id="back", state=MainMenu.MAIN),
    ),
    state=MainMenu.DEVICES,
    getter=devices_getter,
)

device_confirm_delete = Window(
    DynamicMedia("banner"),
    Format("{confirm_message}"),
    Row(
        Button(
            text=Format("{confirm_delete_text}"),
            id="confirm_delete",
            on_click=on_device_delete_confirm,
        ),
        SwitchTo(text=Format("{back_text}"), id="cancel", state=MainMenu.DEVICES),
    ),
    state=MainMenu.DEVICE_CONFIRM_DELETE,
    getter=device_confirm_delete_getter,
)

device_confirm_delete_all = Window(
    DynamicMedia("banner"),
    Format("{confirm_message}"),
    Row(
        Button(
            text=Format("{confirm_delete_text}"),
            id="confirm_delete_all",
            on_click=on_device_delete_all_confirm,
        ),
        SwitchTo(text=Format("{back_text}"), id="cancel", state=MainMenu.DEVICES),
    ),
    state=MainMenu.DEVICE_CONFIRM_DELETE_ALL,
    getter=device_confirm_delete_all_getter,
)

device_confirm_reissue = Window(
    DynamicMedia("banner"),
    Format("{confirm_message}"),
    Row(
        Button(
            text=Format("{confirm_reissue_text}"),
            id="confirm_reissue",
            on_click=on_reissue_subscription_confirm,
        ),
        SwitchTo(text=Format("{cancel_text}"), id="cancel", state=MainMenu.DEVICES),
    ),
    state=MainMenu.DEVICE_CONFIRM_REISSUE,
    getter=device_confirm_reissue_getter,
)

router = Dialog(
    main, devices, device_confirm_delete, device_confirm_delete_all, device_confirm_reissue
)
