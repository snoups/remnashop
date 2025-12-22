from aiogram import Router
from aiogram.filters import ExceptionTypeFilter
from aiogram_dialog.api.exceptions import (
    InvalidStackIdError,
    OutdatedIntent,
    UnknownIntent,
    UnknownState,
)

from . import menu

__all__ = [
    "setup_routers",
]


def setup_routers(router: Router) -> None:
    # WARNING: The order of router registration matters!
    routers = [
        menu.handlers.router,
        menu.dialog.router,
    ]

    router.include_routers(*routers)


def setup_error_handlers(router: Router) -> None:
    pass
