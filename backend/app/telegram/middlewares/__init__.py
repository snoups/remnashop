from aiogram import Router

from app.telegram.middlewares.base import EventTypedMiddleware
from app.telegram.middlewares.blacklist import BlacklistMiddleware
from app.telegram.middlewares.command_gate import CommandGateMiddleware
from app.telegram.middlewares.error import ErrorMiddleware
from app.telegram.middlewares.user import UserMiddleware

__all__ = [
    "setup_middlewares",
]

# Access, Rules, Channel, Throttling, Garbage aren't here yet -- they depend on
# modules/settings (access mode, mandatory channel, rules URL) and Redis-backed
# cache/state tracking, neither of which exist yet. Add them back once those do.


def setup_middlewares(router: Router) -> None:
    outer_middlewares: list[EventTypedMiddleware] = [
        ErrorMiddleware(),
        UserMiddleware(),
        BlacklistMiddleware(),
        CommandGateMiddleware(),
    ]

    for middleware in outer_middlewares:
        middleware.setup_outer(router=router)
