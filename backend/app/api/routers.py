from typing import Final

from fastapi import APIRouter

from app.modules.api_tokens.api import admin_router as api_tokens_admin_router
from app.modules.auth.api import router as auth_router
from app.modules.auth.api import sessions_router as auth_sessions_router
from app.modules.backups.api import admin_router as backups_admin_router
from app.modules.banners.api import admin_router as banners_admin_router
from app.modules.event_log.api import event_log_admin_router
from app.modules.gateways.api import admin_router as gateways_admin_router
from app.modules.oauth.api import admin_router as oauth_admin_router
from app.modules.oauth.api import router as oauth_router
from app.modules.payments.api import admin_router as payments_admin_router
from app.modules.payments.api import public_router as payments_public_router
from app.modules.payments.api import webhook_router as payments_webhook_router
from app.modules.plans.api import admin_router as plans_admin_router
from app.modules.plans.api import public_router as plans_public_router
from app.modules.pricing.api import admin_router as pricing_admin_router
from app.modules.promocodes.api import admin_router as promocodes_admin_router
from app.modules.promocodes.api import public_router as promocodes_public_router
from app.modules.referrals.api import admin_router as referrals_admin_router
from app.modules.referrals.api import public_router as referrals_public_router
from app.modules.settings.api import admin_router as settings_admin_router
from app.modules.settings.api import router as settings_router
from app.modules.subscriptions.api import addons_router as subscriptions_addons_router
from app.modules.subscriptions.api import admin_router as subscriptions_admin_router
from app.modules.subscriptions.api import router as subscriptions_webhook_router
from app.modules.translations.api import admin_router as translations_admin_router
from app.modules.users.api import admin_router as users_admin_router
from app.modules.users.api import admins_router as users_admins_router

# Each further module contributes its router here once it has an api/ package.
ROUTERS: Final[tuple[APIRouter, ...]] = (
    auth_router,
    auth_sessions_router,
    oauth_router,
    oauth_admin_router,
    users_admin_router,
    users_admins_router,
    settings_admin_router,
    settings_router,
    plans_admin_router,
    plans_public_router,
    pricing_admin_router,
    promocodes_admin_router,
    promocodes_public_router,
    referrals_admin_router,
    referrals_public_router,
    subscriptions_admin_router,
    subscriptions_addons_router,
    subscriptions_webhook_router,
    backups_admin_router,
    banners_admin_router,
    event_log_admin_router,
    gateways_admin_router,
    payments_admin_router,
    payments_public_router,
    payments_webhook_router,
    api_tokens_admin_router,
    translations_admin_router,
)
