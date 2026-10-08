from aiogram import Router

from app.telegram.routers import custom, menu, promocode
from app.telegram.routers.broadcasts import handlers as broadcasts_handlers
from app.telegram.routers.requirements import handlers as requirements_handlers


def setup_routers(router: Router) -> None:
    router.include_routers(
        requirements_handlers.router,
        broadcasts_handlers.router,
        menu.handlers.router,
        menu.dialog.router,
        promocode.dialog.router,
        custom.dialog.router,
    )
