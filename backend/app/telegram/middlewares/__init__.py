from aiogram import Router

from app.telegram.middlewares.base import EventTypedMiddleware
from app.telegram.middlewares.blacklist import BlacklistMiddleware
from app.telegram.middlewares.command_gate import CommandGateMiddleware
from app.telegram.middlewares.error import ErrorMiddleware
from app.telegram.middlewares.user import UserMiddleware

__all__ = [
    "setup_middlewares",
]

# Not ported yet: Access, Rules and Channel need settings that don't exist
# (access mode, rules URL, mandatory channel); Throttling and Garbage need nothing
# new, they just haven't been carried over.


def setup_middlewares(router: Router) -> None:
    outer_middlewares: list[EventTypedMiddleware] = [
        ErrorMiddleware(),
        UserMiddleware(),
        BlacklistMiddleware(),
        CommandGateMiddleware(),
    ]

    for middleware in outer_middlewares:
        middleware.setup_outer(router=router)
