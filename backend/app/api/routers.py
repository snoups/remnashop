from typing import Final

from fastapi import APIRouter

from app.modules.account_merge.api import admin_router as account_merge_admin_router
from app.modules.advertising.api import admin_router as advertising_admin_router
from app.modules.analytics.api import admin_router as analytics_admin_router
from app.modules.announcements.api import admin_router as announcements_admin_router
from app.modules.api_tokens.api import admin_router as api_tokens_admin_router
from app.modules.auth.api import router as auth_router
from app.modules.auth.api import sessions_router as auth_sessions_router
from app.modules.auth.api import user_sessions_router as auth_user_sessions_router
from app.modules.backups.api import admin_router as backups_admin_router
from app.modules.banners.api import admin_router as banners_admin_router
from app.modules.blacklist.api import admin_router as blacklist_admin_router
from app.modules.broadcasts.api import admin_router as broadcasts_admin_router
from app.modules.dialogs.api import admin_router as dialogs_admin_router
from app.modules.emoji_packs.api import admin_router as emoji_packs_admin_router
from app.modules.emoji_packs.api import public_router as emoji_packs_public_router
from app.modules.event_log.api import admin_router as event_log_admin_router
from app.modules.gateways.api import admin_router as gateways_admin_router
from app.modules.loyalty.api import admin_router as loyalty_admin_router
from app.modules.notifications.api import admin_router as notifications_admin_router
from app.modules.notifications.api import settings_router as notifications_settings_router
from app.modules.oauth.api import admin_router as oauth_admin_router
from app.modules.oauth.api import router as oauth_router
from app.modules.overview.api import admin_router as overview_admin_router
from app.modules.passkeys.api import admin_router as passkeys_admin_router
from app.modules.passkeys.api import router as passkeys_router
from app.modules.plans.api import addons_router as plans_addons_router
from app.modules.plans.api import admin_router as plans_admin_router
from app.modules.plans.api import pricing_router as plans_pricing_router
from app.modules.promocodes.api import admin_router as promocodes_admin_router
from app.modules.promocodes.api import public_router as promocodes_public_router
from app.modules.referrals.api import admin_router as referrals_admin_router
from app.modules.referrals.api import public_router as referrals_public_router
from app.modules.settings.api import admin_router as settings_admin_router
from app.modules.settings.api import router as settings_router
from app.modules.subscriptions.api import admin_router as subscriptions_admin_router
from app.modules.subscriptions.api import public_router as subscriptions_public_router
from app.modules.subscriptions.api import router as subscriptions_webhook_router
from app.modules.transactions.api import admin_router as transactions_admin_router
from app.modules.transactions.api import public_router as transactions_public_router
from app.modules.transactions.api import webhook_router as transactions_webhook_router
from app.modules.translations.api import admin_router as translations_admin_router
from app.modules.translations.api import locales_router as translations_locales_router
from app.modules.users.api import admin_router as users_admin_router
from app.modules.users.api import admins_router as users_admins_router

# Each further module contributes its router here once it has an api/ package.
ROUTERS: Final[tuple[APIRouter, ...]] = (
    auth_router,
    auth_sessions_router,
    auth_user_sessions_router,
    oauth_router,
    oauth_admin_router,
    passkeys_router,
    passkeys_admin_router,
    users_admin_router,
    users_admins_router,
    account_merge_admin_router,
    settings_admin_router,
    settings_router,
    plans_admin_router,
    plans_addons_router,
    plans_pricing_router,
    promocodes_admin_router,
    promocodes_public_router,
    referrals_admin_router,
    referrals_public_router,
    loyalty_admin_router,
    subscriptions_admin_router,
    subscriptions_public_router,
    subscriptions_webhook_router,
    backups_admin_router,
    banners_admin_router,
    broadcasts_admin_router,
    emoji_packs_admin_router,
    emoji_packs_public_router,
    blacklist_admin_router,
    event_log_admin_router,
    notifications_admin_router,
    notifications_settings_router,
    announcements_admin_router,
    gateways_admin_router,
    transactions_admin_router,
    transactions_public_router,
    transactions_webhook_router,
    api_tokens_admin_router,
    translations_admin_router,
    translations_locales_router,
    dialogs_admin_router,
    advertising_admin_router,
    analytics_admin_router,
    overview_admin_router,
)
