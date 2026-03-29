from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Column, Row, Select, Start, StubScroll, SwitchTo
from magic_filter import F

from src.core.enums import BannerName
from src.telegram.keyboards import main_menu_button
from src.telegram.states import Dashboard, DashboardStatistics
from src.telegram.widgets import Banner, I18nFormat, IgnoreUpdate

from .getters import (
    promocodes_getter,
    referrals_getter,
    subscriptions_getter,
    transactions_getter,
    users_getter,
)
from .handlers import on_gateway_select, on_plan_select

statistics = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-statistics-main"),
    Column(
        SwitchTo(
            text=I18nFormat("btn-statistics.users"),
            id="users",
            state=DashboardStatistics.USERS,
        ),
        SwitchTo(
            text=I18nFormat("btn-statistics.subscriptions"),
            id="subscriptions",
            state=DashboardStatistics.SUBSCRIPTIONS,
        ),
        SwitchTo(
            text=I18nFormat("btn-statistics.transactions"),
            id="transactions",
            state=DashboardStatistics.TRANSACTIONS,
        ),
        SwitchTo(
            text=I18nFormat("btn-statistics.promocodes"),
            id="promocodes",
            state=DashboardStatistics.PROMOCODES,
        ),
        SwitchTo(
            text=I18nFormat("btn-statistics.referrals"),
            id="referrals",
            state=DashboardStatistics.REFERRALS,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=Dashboard.MAIN,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=DashboardStatistics.MAIN,
)

users = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-statistics-users"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardStatistics.MAIN,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=DashboardStatistics.USERS,
    getter=users_getter,
)

subscriptions = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-statistics-subscriptions"),
    StubScroll(id="scroll_subscriptions", pages="pages"),
    Column(
        Select(
            text=I18nFormat(
                "btn-statistics.subscription-page",
                page=F["item"]["page"],
                plan_name=F["item"]["plan_name"],
                is_current=F["item"]["is_current"],
            ),
            id="plan_select",
            item_id_getter=lambda x: x["page"],
            items="pager_pages",
            type_factory=int,
            on_click=on_plan_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardStatistics.MAIN,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=DashboardStatistics.SUBSCRIPTIONS,
    getter=subscriptions_getter,
    preview_data=subscriptions_getter,
)

transactions = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-statistics-transactions"),
    StubScroll(id="scroll_transactions", pages="pages"),
    Column(
        Select(
            text=I18nFormat(
                "btn-statistics.transaction-page",
                page=F["item"]["page"],
                gateway_type=F["item"]["gateway_type"],
                is_current=F["item"]["is_current"],
            ),
            id="gateway_select",
            item_id_getter=lambda x: x["page"],
            items="pager_pages",
            type_factory=int,
            on_click=on_gateway_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardStatistics.MAIN,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=DashboardStatistics.TRANSACTIONS,
    getter=transactions_getter,
    preview_data=transactions_getter,
)

promocodes = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-statistics-promocodes"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardStatistics.MAIN,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=DashboardStatistics.PROMOCODES,
    getter=promocodes_getter,
)

referrals = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-statistics-referrals"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardStatistics.MAIN,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=DashboardStatistics.REFERRALS,
    getter=referrals_getter,
)

router = Dialog(
    statistics,
    users,
    subscriptions,
    transactions,
    promocodes,
    referrals,
)
