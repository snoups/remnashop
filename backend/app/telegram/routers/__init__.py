from aiogram import Router

from app.telegram.routers import (
    custom,
    errors,
    menu,
    payment_result,
    promocode,
    purchase,
    referrals,
    subscriptions,
)
from app.telegram.routers.bot_member import handlers as bot_member_handlers
from app.telegram.routers.broadcasts import handlers as broadcasts_handlers
from app.telegram.routers.cabinet_auth import handlers as cabinet_auth_handlers
from app.telegram.routers.legal import handlers as legal_handlers
from app.telegram.routers.payments import handlers as payments_handlers
from app.telegram.routers.purchase import deeplink as plan_link
from app.telegram.routers.requirements import handlers as requirements_handlers


def setup_routers(router: Router) -> None:
    router.include_routers(
        errors.router,
        bot_member_handlers.router,
        payments_handlers.router,
        requirements_handlers.router,
        broadcasts_handlers.router,
        cabinet_auth_handlers.router,
        plan_link.router,
        legal_handlers.router,
        menu.handlers.router,
        menu.dialog.router,
        subscriptions.dialog.router,
        purchase.dialog.router,
        payment_result.dialog.router,
        promocode.dialog.router,
        referrals.dialog.router,
        custom.dialog.router,
    )
