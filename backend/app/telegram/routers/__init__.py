from aiogram import Router

from app.telegram.routers import menu, promocode


def setup_routers(router: Router) -> None:
    router.include_routers(
        menu.handlers.router,
        menu.dialog.router,
        promocode.dialog.router,
    )
