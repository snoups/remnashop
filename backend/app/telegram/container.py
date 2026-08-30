from aiogram import Bot
from aiogram_dialog import BgManagerFactory
from dishka import AsyncContainer, make_async_container
from dishka.integrations.aiogram import AiogramProvider

from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.modules.banners import get_banners_providers
from app.modules.settings import get_settings_providers
from app.modules.users import get_user_providers


def create_aiogram_container(
    config: AppConfig,
    bg_manager_factory: BgManagerFactory,
    bot: Bot,
) -> AsyncContainer:
    context = {
        AppConfig: config,
        BgManagerFactory: bg_manager_factory,
        Bot: bot,
    }
    providers = [
        AiogramProvider(),
        *get_core_providers(),
        *get_user_providers(),
        *get_settings_providers(),
        *get_banners_providers(),
    ]
    return make_async_container(*providers, context=context)
