from aiogram import Bot
from aiogram_dialog import BgManagerFactory
from dishka import AsyncContainer, make_async_container
from dishka.integrations.aiogram import AiogramProvider
from fluentogram import TranslatorHub

from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.modules.banners import get_banners_providers
from app.modules.blacklist import get_blacklist_providers
from app.modules.plans import get_plans_providers
from app.modules.promocodes import get_promocodes_providers
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
    providers = [
        AiogramProvider(),
        *get_core_providers(),
        *get_users_providers(),
        *get_settings_providers(),
        *get_banners_providers(),
        *get_subscriptions_providers(),
        *get_promocodes_providers(),
        *get_plans_providers(),
        *get_blacklist_providers(),
        DialogConfigProvider(),
    ]
    return make_async_container(*providers, context=context)
