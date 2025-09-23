from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.kbd import Button, Column, Row, Select, Start, SwitchTo
from magic_filter import F

from src.bot.states import Dashboard, DashboardUser
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName, UserRole

from .getters import role_getter, user_getter
from .handlers import on_block_toggle, on_role_selected

# TODO: Implement a button that adds the user to the access plan's allowed users list
user = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-main"),
    Row(
        Button(
            text=I18nFormat("btn-user-statistics"),
            id="statistics",
        ),
        Button(
            text=I18nFormat("btn-user-message"),
            id="message",
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-user-subscription"),
            id="subscription",
        ),
        Button(
            text=I18nFormat("btn-user-transactions"),
            id="transactions",
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-user-role"),
            id="role",
            state=DashboardUser.ROLE,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-user-block", is_blocked=F["is_blocked"]),
            id="block",
            on_click=on_block_toggle,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back-dashboard"),
            id="back",
            state=Dashboard.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.MAIN,
    getter=user_getter,
)

role = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-role"),
    Column(
        Select(
            text=I18nFormat("btn-user-role-choice", role=F["item"]),
            id="select_role",
            item_id_getter=lambda item: item.value,
            items="roles",
            type_factory=UserRole,
            on_click=on_role_selected,
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

router = Dialog(
    user,
    role,
)
