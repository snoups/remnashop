from dishka import AsyncContainer, make_async_container

from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.modules.api_tokens import get_api_tokens_providers
from app.modules.auth import get_auth_providers
from app.modules.banners import get_banners_providers
from app.modules.event_log import get_event_log_providers
from app.modules.gateways import get_gateways_providers
from app.modules.payments import get_payments_providers
from app.modules.plans import get_plans_providers
from app.modules.promocodes import get_promocodes_providers
from app.modules.referrals import get_referrals_providers
from app.modules.settings import get_settings_providers
from app.modules.subscriptions import get_subscriptions_providers
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers


def create_api_container(config: AppConfig) -> AsyncContainer:
    context = {AppConfig: config}
    providers = [
        *get_core_providers(),
        *get_users_providers(),
        *get_auth_providers(),
        *get_settings_providers(),
        *get_plans_providers(),
        *get_promocodes_providers(),
        *get_referrals_providers(),
        *get_subscriptions_providers(),
        *get_banners_providers(),
        *get_event_log_providers(),
        *get_gateways_providers(),
        *get_payments_providers(),
        *get_api_tokens_providers(),
        *get_translations_providers(),
    ]
    return make_async_container(*providers, context=context)
