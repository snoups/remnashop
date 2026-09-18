from aiogram import Router

from app.telegram.routers import custom, menu, promocode


def setup_routers(router: Router) -> None:
    router.include_routers(
        menu.handlers.router,
        menu.dialog.router,
        promocode.dialog.router,
        custom.dialog.router,
    )
