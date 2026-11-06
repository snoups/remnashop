from aiogram import Bot
from aiogram_dialog import BgManagerFactory
from dishka import AsyncContainer, make_async_container
from dishka.integrations.aiogram import AiogramProvider
from fluentogram import TranslatorHub

from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.modules.providers import get_module_providers
from app.telegram.dialogs.di import DialogConfigProvider
from app.telegram.settings_cache import SettingsCacheProvider


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
    return make_async_container(
        AiogramProvider(),
        *get_core_providers(),
        *get_module_providers(),
        DialogConfigProvider(),
        SettingsCacheProvider(),
        context=context,
    )
