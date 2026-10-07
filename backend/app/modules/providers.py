from dishka import Provider

from app.modules.advertising import get_advertising_providers
from app.modules.analytics import get_analytics_providers
from app.modules.announcements import get_announcements_providers
from app.modules.api_tokens import get_api_tokens_providers
from app.modules.auth import get_auth_providers
from app.modules.backups import get_backups_providers
from app.modules.banners import get_banners_providers
from app.modules.blacklist import get_blacklist_providers
from app.modules.dialogs import get_dialogs_providers
from app.modules.emoji_packs import get_emoji_packs_providers
from app.modules.event_log import get_event_log_providers
from app.modules.gateways import get_gateways_providers
from app.modules.loyalty import get_loyalty_providers
from app.modules.notifications import get_notifications_providers
from app.modules.oauth import get_oauth_providers
from app.modules.overview import get_overview_providers
from app.modules.passkeys import get_passkeys_providers
from app.modules.plans import get_plans_providers
from app.modules.pricing import get_pricing_providers
from app.modules.promocodes import get_promocodes_providers
from app.modules.referrals import get_referrals_providers
from app.modules.settings import get_settings_providers
from app.modules.subscriptions import get_subscriptions_providers
from app.modules.transactions import get_transactions_providers
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers


def get_module_providers() -> list[Provider]:
    # every process gets the whole graph: usecases are request-scoped and built
    # on demand, and dishka validates the full graph once at container build
    return [
        *get_users_providers(),
        *get_auth_providers(),
        *get_oauth_providers(),
        *get_passkeys_providers(),
        *get_settings_providers(),
        *get_plans_providers(),
        *get_pricing_providers(),
        *get_promocodes_providers(),
        *get_referrals_providers(),
        *get_loyalty_providers(),
        *get_notifications_providers(),
        *get_backups_providers(),
        *get_subscriptions_providers(),
        *get_banners_providers(),
        *get_emoji_packs_providers(),
        *get_event_log_providers(),
        *get_gateways_providers(),
        *get_transactions_providers(),
        *get_api_tokens_providers(),
        *get_translations_providers(),
        *get_dialogs_providers(),
        *get_blacklist_providers(),
        *get_advertising_providers(),
        *get_analytics_providers(),
        *get_overview_providers(),
        *get_announcements_providers(),
    ]
