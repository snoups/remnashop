from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Button, Column, Row, Select, Start, SwitchTo
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.core.enums import BannerName, SystemNotificationType, UserNotificationType
from src.telegram.keyboards import main_menu_button
from src.telegram.states import DashboardRemnashop, RemnashopNotifications
from src.telegram.widgets import Banner, I18nFormat, IgnoreUpdate

from .getters import system_route_getter, system_type_getter, system_types_getter, user_types_getter
from .handlers import (
    on_chat_id_entered,
    on_invalid_int,
    on_route_clear,
    on_system_route_edit_chat,
    on_system_route_edit_thread,
    on_system_type_select,
    on_system_type_toggle,
    on_thread_id_entered,
    on_user_type_select,
)

notifications = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-notifications-main"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-notifications.user"),
            id="users",
            state=RemnashopNotifications.USER,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-notifications.system"),
            id="system",
            state=RemnashopNotifications.SYSTEM,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardRemnashop.MAIN,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=RemnashopNotifications.MAIN,
)

user = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-notifications-user"),
    Column(
        Select(
            text=I18nFormat(
                "btn-notifications.user-choice",
                type=F["item"]["type"],
                enabled=F["item"]["enabled"],
            ),
            id="type_select",
            item_id_getter=lambda item: item["type"],
            items="types",
            type_factory=UserNotificationType,
            on_click=on_user_type_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=RemnashopNotifications.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopNotifications.USER,
    getter=user_types_getter,
)

# Список системных типов — клик открывает подменю типа
system = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-notifications-system"),
    Column(
        Select(
            text=Format("{item[label]}"),
            id="type_select",
            item_id_getter=lambda item: item["type"],
            items="types",
            on_click=on_system_type_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=RemnashopNotifications.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopNotifications.SYSTEM,
    getter=system_types_getter,
)

# Подменю конкретного типа: тоггл + маршрут
system_type = Window(
    Banner(BannerName.DASHBOARD),
    Format(
        "<b>{ntf_type}</b>\n\n"
        "Статус: {status}\n"
        "Маршрут: {route_info}"
    ),
    Row(
        Button(
            text=Format("{toggle_btn}"),
            id="toggle",
            on_click=on_system_type_toggle,
        ),
        SwitchTo(
            text=Format("📡 Маршрут"),
            id="route",
            state=RemnashopNotifications.SYSTEM_ROUTE,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=RemnashopNotifications.SYSTEM,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopNotifications.SYSTEM_TYPE,
    getter=system_type_getter,
)

# Настройка маршрута
system_route = Window(
    Banner(BannerName.DASHBOARD),
    Format(
        "📡 <b>Маршрут: {ntf_type}</b>\n\n"
        "Chat ID: <code>{chat_id}</code>\n"
        "Thread ID: <code>{thread_id}</code>\n\n"
        "<i>Если маршрут не задан — уведомление идёт в личку админам</i>"
    ),
    Row(
        Button(
            text=Format("✏️ Chat ID"),
            id="edit_chat",
            on_click=on_system_route_edit_chat,
        ),
        Button(
            text=Format("✏️ Thread ID"),
            id="edit_thread",
            on_click=on_system_route_edit_thread,
        ),
    ),
    Row(
        Button(
            text=Format("🗑 Удалить маршрут"),
            id="clear_route",
            on_click=on_route_clear,
            when=F["has_route"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=RemnashopNotifications.SYSTEM_TYPE,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopNotifications.SYSTEM_ROUTE,
    getter=system_route_getter,
)

system_route_chat_id = Window(
    Banner(BannerName.DASHBOARD),
    Format(
        "Введи <b>Chat ID</b> группы\n"
        "(отрицательное число, например <code>-1001234567890</code>):"
    ),
    TextInput(
        id="chat_id_input",
        type_factory=int,
        on_success=on_chat_id_entered,
        on_error=on_invalid_int,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=RemnashopNotifications.SYSTEM_ROUTE,
        ),
    ),
    state=RemnashopNotifications.SYSTEM_ROUTE_CHAT_ID,
    getter=system_route_getter,
)

system_route_thread_id = Window(
    Banner(BannerName.DASHBOARD),
    Format(
        "Введи <b>Thread ID</b> топика\n"
        "(число, введи <code>0</code> чтобы сбросить):"
    ),
    TextInput(
        id="thread_id_input",
        type_factory=int,
        on_success=on_thread_id_entered,
        on_error=on_invalid_int,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=RemnashopNotifications.SYSTEM_ROUTE,
        ),
    ),
    state=RemnashopNotifications.SYSTEM_ROUTE_THREAD_ID,
    getter=system_route_getter,
)

router = Dialog(
    notifications,
    user,
    system,
    system_type,
    system_route,
    system_route_chat_id,
    system_route_thread_id,
)
