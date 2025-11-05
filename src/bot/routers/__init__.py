from aiogram import Router
from aiogram.filters import ExceptionTypeFilter
from aiogram_dialog.api.exceptions import UnknownIntent, UnknownState

from src.bot.routers.extra.error import on_unknown_intent, on_unknown_state

from . import dashboard, extra, menu, subscription
from .dashboard import (
    access,
    broadcast,
    importer,
    promocodes,
    remnashop,
    remnawave,
    statistics,
    users,
)

__all__ = [
    "setup_routers",
]


def setup_routers(router: Router) -> None:
    # WARNING: The order of router registration matters!
    routers = [
        extra.payment.router,
        extra.notification.router,
        extra.test.router,
        extra.member.router,
        extra.goto.router,
        #
        menu.handlers.router,
        menu.dialog.router,
        #
        subscription.dialog.router,
        #
        dashboard.dialog.router,
        statistics.dialog.router,
        access.dialog.router,
        broadcast.dialog.router,
        promocodes.dialog.router,
        #
        remnashop.dialog.router,
        remnashop.gateways.dialog.router,
        remnashop.notifications.dialog.router,
        remnashop.plans.dialog.router,
        #
        remnawave.dialog.router,
        #
        importer.dialog.router,
        #
        users.dialog.router,
        users.user.dialog.router,
    ]

    router.include_routers(*routers)


def setup_error_handlers(router: Router) -> None:
    router.errors.register(on_unknown_intent, ExceptionTypeFilter(UnknownIntent))
    router.errors.register(on_unknown_state, ExceptionTypeFilter(UnknownState))
