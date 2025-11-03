from aiogram import Router

from src.bot.middlewares.base import EventTypedMiddleware

from .access import AccessMiddleware
from .channel import ChannelMiddleware
from .error import ErrorMiddleware
from .garbage import GarbageMiddleware
from .rules import RulesMiddleware
from .throttling import ThrottlingMiddleware
from .user import UserMiddleware

__all__ = [
    "setup_middlewares",
]


def setup_middlewares(router: Router) -> None:
    outer_middlewares: list[EventTypedMiddleware] = [
        ErrorMiddleware(),
        AccessMiddleware(),
        RulesMiddleware(),
        UserMiddleware(),
        ChannelMiddleware(),
        ThrottlingMiddleware(),
    ]
    inner_middlewares: list[EventTypedMiddleware] = [
        GarbageMiddleware(),
    ]

    for middleware in outer_middlewares:
        middleware.setup_outer(router=router)

    for middleware in inner_middlewares:
        middleware.setup_inner(router=router)
