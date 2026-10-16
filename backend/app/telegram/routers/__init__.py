from aiogram import Router

from app.telegram.routers import custom, menu, promocode, purchase, referrals, subscriptions
from app.telegram.routers.bot_member import handlers as bot_member_handlers
from app.telegram.routers.broadcasts import handlers as broadcasts_handlers
from app.telegram.routers.cabinet_auth import handlers as cabinet_auth_handlers
from app.telegram.routers.payments import handlers as payments_handlers
from app.telegram.routers.requirements import handlers as requirements_handlers


def setup_routers(router: Router) -> None:
    router.include_routers(
        bot_member_handlers.router,
        payments_handlers.router,
        requirements_handlers.router,
        broadcasts_handlers.router,
        cabinet_auth_handlers.router,
        menu.handlers.router,
        menu.dialog.router,
        subscriptions.dialog.router,
        purchase.dialog.router,
        promocode.dialog.router,
        referrals.dialog.router,
        custom.dialog.router,
    )
