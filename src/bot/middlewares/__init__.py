from aiogram import Router

from src.bot.middlewares.base import EventTypedMiddleware

from .error import ErrorMiddleware
from .garbage import GarbageMiddleware
from .maintenance import MaintenanceMiddleware
from .throttling import ThrottlingMiddleware
from .user import UserMiddleware

__all__ = [
    "setup_middlewares",
]

# TODO: Create middleware for rules and banlist(rework Maintenance) and ?channel sub?


def setup_middlewares(router: Router) -> None:
    outer_middlewares: list[EventTypedMiddleware] = [
        ErrorMiddleware(),
        UserMiddleware(),
        ThrottlingMiddleware(),
        MaintenanceMiddleware(),
    ]
    inner_middlewares: list[EventTypedMiddleware] = [
        GarbageMiddleware(),
    ]

    for middleware in outer_middlewares:
        middleware.setup_outer(router=router)

    for middleware in inner_middlewares:
        middleware.setup_inner(router=router)
