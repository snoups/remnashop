from aiogram import Bot
from aiogram_dialog import BgManagerFactory
from dishka import AsyncContainer, Provider, Scope, make_async_container
from dishka.integrations.aiogram import AiogramProvider
from fluentogram import TranslatorHub

from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.core.ports import SessionRevoker
from app.modules.auth import SessionRepository
from app.modules.banners import get_banners_providers
from app.modules.blacklist import get_blacklist_providers
from app.modules.passkeys import get_passkey_revoker_providers
from app.modules.payments import PaymentOrderRepository
from app.modules.plans import get_plans_providers
from app.modules.pricing import get_pricing_providers
from app.modules.promocodes import get_promocodes_providers
from app.modules.referrals import get_referrals_providers
from app.modules.settings import get_settings_providers
from app.modules.subscriptions import get_subscriptions_providers
from app.modules.users import get_users_providers
from app.telegram.dialogs.di import DialogConfigProvider


def create_aiogram_container(
    config: AppConfig,
    bg_manager_factory: BgManagerFactory,
    bot: Bot,
    translator_hub: TranslatorHub,
) -> AsyncContainer:
    context = {
        AppConfig: config,
        BgManagerFactory: bg_manager_factory,
        Bot: bot,
        TranslatorHub: translator_hub,
    }
    # SessionRevoker directly, not via get_auth_providers() -- that also
    # registers the login/refresh usecase graph the bot never serves. Needed
    # because get_users_providers() registers admin usecases that revoke
    # sessions. get_passkey_revoker_providers() is here for the same reason:
    # demoting an admin drops their passkeys, and the bot never serves
    # passkey auth.
    session_revoker_provider = Provider(scope=Scope.REQUEST)
    session_revoker_provider.provide(SessionRepository)
    session_revoker_provider.alias(source=SessionRepository, provides=SessionRevoker)
    # GetPromocodeSummaryUseCase (registered by get_promocodes_providers())
    # reads payment orders; the bot never serves it, so no payments usecases.
    payment_orders_provider = Provider(scope=Scope.REQUEST)
    payment_orders_provider.provide(PaymentOrderRepository)

    providers = [
        AiogramProvider(),
        *get_core_providers(),
        *get_users_providers(),
        *get_passkey_revoker_providers(),
        *get_settings_providers(),
        *get_banners_providers(),
        *get_subscriptions_providers(),
        *get_promocodes_providers(),
        *get_referrals_providers(),
        *get_plans_providers(),
        *get_pricing_providers(),
        *get_blacklist_providers(),
        DialogConfigProvider(),
        session_revoker_provider,
        payment_orders_provider,
    ]
    return make_async_container(*providers, context=context)
