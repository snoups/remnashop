from uuid import UUID

from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (
    Button,
    Column,
    CopyText,
    Group,
    ListGroup,
    Row,
    ScrollingGroup,
    Select,
    Start,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.keyboards import back_main_menu_button
from src.bot.routers.dashboard.broadcast.handlers import on_content_input, on_preview
from src.bot.routers.extra.test import show_dev_popup
from src.bot.states import DashboardUser, DashboardUsers
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName, SubscriptionStatus, UserRole

from .getters import (
    device_limit_getter,
    devices_getter,
    discount_getter,
    expire_time_getter,
    give_access_getter,
    role_getter,
    squads_getter,
    subscription_getter,
    traffic_limit_getter,
    transaction_getter,
    transactions_getter,
    user_getter,
)
from .handlers import (
    on_active_toggle,
    on_block_toggle,
    on_current_subscription,
    on_device_delete,
    on_device_limit_input,
    on_device_limit_select,
    on_devices,
    on_discount_input,
    on_discount_select,
    on_duration_input,
    on_duration_select,
    on_give_access,
    on_plan_select,
    on_reset_traffic,
    on_role_select,
    on_send,
    on_squad_select,
    on_subscription_delete,
    on_traffic_limit_input,
    on_traffic_limit_select,
    on_transaction_select,
    on_transactions,
)

user = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-main"),
    Row(
        Button(
            text=I18nFormat("btn-user-current-subscription"),
            id="subscription",
            on_click=on_current_subscription,
            when=F["has_subscription"],
        ),
        Button(
            text=I18nFormat("btn-user-statistics"),
            id="statistics",
            on_click=show_dev_popup,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-user-transactions"),
            id="transactions",
            on_click=on_transactions,
        ),
        SwitchTo(
            text=I18nFormat("btn-user-message"),
            id="message",
            state=DashboardUser.MESSAGE,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-user-discount"),
            id="discount",
            state=DashboardUser.DISCOUNT,
        ),
        Button(
            text=I18nFormat("btn-user-give-access"),
            id="give_access",
            on_click=on_give_access,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-user-role"),
            id="role",
            state=DashboardUser.ROLE,
            when=F["is_not_self"] & F["can_edit"],
        ),
        Button(
            text=I18nFormat("btn-user-block", is_blocked=F["is_blocked"]),
            id="block",
            on_click=on_block_toggle,
            when=F["is_not_self"] & F["can_edit"],
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back-dashboard"),
            id="back",
            state=DashboardUsers.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=DashboardUser.MAIN,
    getter=user_getter,
)

subscription = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-subscription-info"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-user-subscription-traffic-limit"),
            id="traffic",
            state=DashboardUser.TRAFFIC_LIMIT,
        ),
        SwitchTo(
            text=I18nFormat("btn-user-subscription-device-limit"),
            id="device",
            state=DashboardUser.DEVICE_LIMIT,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-user-subscription-traffic-reset"),
            id="reset",
            on_click=on_reset_traffic,
        ),
        Button(
            text=I18nFormat("btn-user-subscription-devices"),
            id="devices",
            on_click=on_devices,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-user-subscription-expire-time"),
            id="expire_time",
            state=DashboardUser.EXPIRE_TIME,
        ),
        SwitchTo(
            text=I18nFormat("btn-user-subscription-squads"),
            id="squads",
            state=DashboardUser.SQUADS,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-user-subscription-active-toggle", is_active=F["is_active"]),
            id="active_toggle",
            on_click=on_active_toggle,
            when=F["subscription_status"].in_(
                [SubscriptionStatus.ACTIVE, SubscriptionStatus.DISABLED]
            ),
        ),
        Button(
            text=I18nFormat("btn-user-subscription-delete"),
            id="delete",
            on_click=on_subscription_delete,
        ),
    ),
    Row(
        CopyText(
            text=I18nFormat("btn-user-subscription-url"),
            copy_text=Format("{url}"),
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.SUBSCRIPTION,
    getter=subscription_getter,
)

traffic_limit = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-subscription-traffic-limit"),
    Group(
        Select(
            text=I18nFormat("{item[traffic_limit][0]}", value=F["item"]["traffic"]),
            id="traffic_limit_select",
            item_id_getter=lambda item: item["traffic"],
            items="traffic_count",
            type_factory=int,
            on_click=on_traffic_limit_select,
        ),
        width=3,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.SUBSCRIPTION,
        ),
    ),
    MessageInput(func=on_traffic_limit_input),
    IgnoreUpdate(),
    state=DashboardUser.TRAFFIC_LIMIT,
    getter=traffic_limit_getter,
)

device_limit = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-subscription-device-limit"),
    Group(
        Select(
            text=I18nFormat("unit-device", value=F["item"]),
            id="device_limit_select",
            item_id_getter=lambda item: item,
            items="devices_count",
            type_factory=int,
            on_click=on_device_limit_select,
        ),
        width=3,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.SUBSCRIPTION,
        ),
    ),
    MessageInput(func=on_device_limit_input),
    IgnoreUpdate(),
    state=DashboardUser.DEVICE_LIMIT,
    getter=device_limit_getter,
)

expire_time = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-subscription-expire-time"),
    Group(
        Select(
            text=I18nFormat(
                "btn-user-subscription-duration",
                operation=F["item"]["operation"],
                duration=F["item"]["duration"],
            ),
            id="duration_select",
            item_id_getter=lambda item: item["days"],
            items="durations",
            type_factory=int,
            on_click=on_duration_select,
        ),
        width=2,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.SUBSCRIPTION,
        ),
    ),
    MessageInput(func=on_duration_input),
    IgnoreUpdate(),
    state=DashboardUser.EXPIRE_TIME,
    getter=expire_time_getter,
)

squads = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-subscription-squads"),
    Column(
        Select(
            text=I18nFormat(
                "btn-squad-choice",
                name=F["item"]["name"],
                selected=F["item"]["selected"],
            ),
            id="select_squad",
            item_id_getter=lambda item: item["uuid"],
            items="squads",
            type_factory=UUID,
            on_click=on_squad_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.SUBSCRIPTION,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.SQUADS,
    getter=squads_getter,
)

devices_list = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-devices"),
    ListGroup(
        Row(
            CopyText(
                text=Format("{item[platform]} - {item[device_model]}"),
                copy_text=Format("{item[user_agent]}"),
            ),
            Button(
                text=Format("❌"),
                id="delete",
                on_click=on_device_delete,
            ),
        ),
        id="devices_list",
        item_id_getter=lambda item: item["hwid"],
        items="devices",
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.SUBSCRIPTION,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.DEVICES_LIST,
    getter=devices_getter,
)

discount = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-discount"),
    Group(
        Select(
            text=Format("{item}%"),
            id="discount_select",
            item_id_getter=lambda item: item,
            items="percentages",
            type_factory=int,
            on_click=on_discount_select,
        ),
        width=3,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    MessageInput(func=on_discount_input),
    IgnoreUpdate(),
    state=DashboardUser.DISCOUNT,
    getter=discount_getter,
)

transactions_list = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-transactions"),
    ScrollingGroup(
        Select(
            text=I18nFormat(
                "btn-user-transaction",
                status=F["item"]["status"],
                created_at=F["item"]["created_at"],
            ),
            id="transaction_select",
            item_id_getter=lambda item: item["payment_id"],
            items="transactions",
            type_factory=UUID,
            on_click=on_transaction_select,
        ),
        id="scroll",
        width=1,
        height=7,
        hide_on_single_page=True,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.TRANSACTIONS_LIST,
    getter=transactions_getter,
)

transaction = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-transaction-info"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.TRANSACTIONS_LIST,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.TRANSACTION,
    getter=transaction_getter,
)

role = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-role"),
    Column(
        Select(
            text=I18nFormat("role", role=F["item"]),
            id="role_select",
            item_id_getter=lambda item: item.value,
            items="roles",
            type_factory=UserRole,
            on_click=on_role_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.ROLE,
    getter=role_getter,
)

give_access = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-give-access"),
    Select(
        text=I18nFormat(
            "btn-user-allowed-plan-choice",
            plan_name=F["item"]["plan_name"],
            selected=F["item"]["selected"],
        ),
        id="plan_select",
        item_id_getter=lambda item: item["plan_id"],
        items="plans",
        type_factory=int,
        on_click=on_plan_select,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.GIVE_ACCESS,
    getter=give_access_getter,
)

message = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-message"),
    Row(
        Button(
            I18nFormat("btn-user-message-preview"),
            id="preview",
            on_click=on_preview,
        ),
    ),
    Row(
        Button(
            I18nFormat("btn-user-message-confirm"),
            id="confirm",
            on_click=on_send,
        ),
    ),
    Row(
        SwitchTo(
            I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    MessageInput(func=on_content_input),
    IgnoreUpdate(),
    state=DashboardUser.MESSAGE,
)

router = Dialog(
    user,
    subscription,
    traffic_limit,
    device_limit,
    devices_list,
    expire_time,
    squads,
    discount,
    transactions_list,
    transaction,
    role,
    give_access,
    message,
)
