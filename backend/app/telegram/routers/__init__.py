from aiogram import Router

from app.telegram.routers.menu.handlers import router as menu_router


def setup_routers(router: Router) -> None:
    router.include_routers(menu_router)
