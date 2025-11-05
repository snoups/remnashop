from uuid import UUID

from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (
    Button,
    Column,
    ListGroup,
    Row,
    ScrollingGroup,
    Select,
    Start,
    SwitchTo,
)
from magic_filter import F

from src.bot.keyboards import main_menu_button
from src.bot.states import Dashboard, DashboardBroadcast
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName, BroadcastAudience, BroadcastStatus

from .getters import buttons_getter, list_getter, plans_getter, send_getter, view_getter
from .handlers import (
    on_audience_select,
    on_broadcast_list,
    on_broadcast_select,
    on_button_select,
    on_cancel,
    on_content_input,
    on_delete,
    on_plan_select,
    on_preview,
    on_send,
)

broadcast = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-broadcast-main"),
    Row(
        Button(
            I18nFormat("btn-broadcast-list"),
            id="list",
            on_click=on_broadcast_list,
        ),
    ),
    Row(
        Button(
            I18nFormat("btn-broadcast-all"),
            id=BroadcastAudience.ALL,
            on_click=on_audience_select,
        ),
        Button(
            I18nFormat("btn-broadcast-plan"),
            id=BroadcastAudience.PLAN,
            on_click=on_audience_select,
        ),
    ),
    Row(
        Button(
            I18nFormat("btn-broadcast-subscribed"),
            id=BroadcastAudience.SUBSCRIBED,
            on_click=on_audience_select,
        ),
        Button(
            I18nFormat("btn-broadcast-unsubscribed"),
            id=BroadcastAudience.UNSUBSCRIBED,
            on_click=on_audience_select,
        ),
    ),
    Row(
        Button(
            I18nFormat("btn-broadcast-expired"),
            id=BroadcastAudience.EXPIRED,
            on_click=on_audience_select,
        ),
        Button(
            I18nFormat("btn-broadcast-trial"),
            id=BroadcastAudience.TRIAL,
            on_click=on_audience_select,
        ),
    ),
    Row(
        Start(
            I18nFormat("btn-back"),
            id="back",
            state=Dashboard.MAIN,
            mode=StartMode.RESET_STACK,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=DashboardBroadcast.MAIN,
)

list = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-broadcast-list"),
    ScrollingGroup(
        Select(
            text=I18nFormat(
                "btn-broadcast",
                status=F["item"]["status"],
                created_at=F["item"]["created_at"],
            ),
            id="broadcast",
            item_id_getter=lambda item: item["task_id"],
            items="broadcasts",
            type_factory=UUID,
            on_click=on_broadcast_select,
        ),
        id="scroll",
        width=1,
        height=7,
        hide_on_single_page=True,
    ),
    Row(
        Start(
            I18nFormat("btn-back"),
            id="back",
            state=DashboardBroadcast.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardBroadcast.LIST,
    getter=list_getter,
)

view = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-broadcast-view"),
    Row(
        SwitchTo(
            I18nFormat("btn-broadcast-refresh"),
            id="refresh",
            state=DashboardBroadcast.VIEW,
            when=F["broadcast_status"] == BroadcastStatus.PROCESSING,
        ),
    ),
    Row(
        Button(
            I18nFormat("btn-broadcast-viewing"),
            id="preview",
            on_click=on_preview,
        ),
    ),
    Row(
        Button(
            I18nFormat("btn-broadcast-cancel"),
            id="cancel",
            on_click=on_cancel,
            when=F["broadcast_status"] == BroadcastStatus.PROCESSING,
        ),
    ),
    Row(
        Button(
            I18nFormat("btn-broadcast-delete"),
            id="delete",
            on_click=on_delete,
            when=F["broadcast_status"].in_(
                [BroadcastStatus.COMPLETED, BroadcastStatus.CANCELED, BroadcastStatus.ERROR]
            ),
        ),
    ),
    Row(
        SwitchTo(
            I18nFormat("btn-back"),
            id="back",
            state=DashboardBroadcast.LIST,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardBroadcast.VIEW,
    getter=view_getter,
)

plan = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-broadcast-plan-choice"),
    Column(
        Select(
            text=I18nFormat(
                "btn-plan",
                name=F["item"]["name"],
                is_active=F["item"]["is_active"],
            ),
            id="plans_list",
            item_id_getter=lambda item: item["id"],
            items="plans",
            type_factory=int,
            on_click=on_plan_select,
        ),
    ),
    Row(
        Start(
            I18nFormat("btn-back"),
            id="back",
            state=DashboardBroadcast.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardBroadcast.PLAN,
    getter=plans_getter,
)

send = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-broadcast-send"),
    Row(
        SwitchTo(
            I18nFormat("btn-broadcast-content"),
            id="content",
            state=DashboardBroadcast.CONTENT,
        ),
    ),
    Row(
        Button(
            I18nFormat("btn-broadcast-preview"),
            id="preview",
            on_click=on_preview,
        ),
    ),
    Row(
        Button(
            I18nFormat("btn-broadcast-confirm"),
            id="confirm",
            on_click=on_send,
        ),
    ),
    Row(
        Start(
            I18nFormat("btn-back"),
            id="back",
            state=DashboardBroadcast.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardBroadcast.SEND,
    getter=send_getter,
)

content = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-broadcast-content"),
    Row(
        SwitchTo(
            I18nFormat("btn-broadcast-buttons"),
            id="buttons",
            state=DashboardBroadcast.BUTTONS,
        ),
    ),
    Row(
        SwitchTo(
            I18nFormat("btn-back"),
            id="back",
            state=DashboardBroadcast.SEND,
        ),
    ),
    MessageInput(func=on_content_input),
    IgnoreUpdate(),
    state=DashboardBroadcast.CONTENT,
)

buttons = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-broadcast-buttons"),
    ListGroup(
        Row(
            Button(
                text=I18nFormat("{item[text]}"),
                id="preview_button",
            ),
            Button(
                text=I18nFormat("btn-broadcast-button-choice", selected=F["item"]["selected"]),
                id="select_button",
                on_click=on_button_select,
            ),
        ),
        id="button_list",
        item_id_getter=lambda item: item["id"],
        items="buttons",
    ),
    Row(
        SwitchTo(
            I18nFormat("btn-back"),
            id="back",
            state=DashboardBroadcast.CONTENT,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardBroadcast.BUTTONS,
    getter=buttons_getter,
)

router = Dialog(
    broadcast,
    list,
    view,
    plan,
    send,
    content,
    buttons,
)
