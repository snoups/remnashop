from aiogram import Router

from app.telegram.middlewares.access import AccessMiddleware
from app.telegram.middlewares.base import EventTypedMiddleware
from app.telegram.middlewares.blacklist import BlacklistMiddleware
from app.telegram.middlewares.command_gate import CommandGateMiddleware
from app.telegram.middlewares.error import ErrorMiddleware
from app.telegram.middlewares.garbage import GarbageMiddleware
from app.telegram.middlewares.requirements import RequirementsMiddleware
from app.telegram.middlewares.user import DialogUserMiddleware, UserMiddleware

__all__ = [
    "setup_middlewares",
]


def setup_middlewares(router: Router) -> None:
    outer_middlewares: list[EventTypedMiddleware] = [
        ErrorMiddleware(),
        UserMiddleware(),
        DialogUserMiddleware(),
        BlacklistMiddleware(),
        AccessMiddleware(),
        RequirementsMiddleware(),
        CommandGateMiddleware(),
    ]

    for middleware in outer_middlewares:
        middleware.setup_outer(router=router)

    # inner: only a message some handler took is deleted
    GarbageMiddleware().setup_inner(router=router)
