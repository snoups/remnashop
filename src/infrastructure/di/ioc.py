from aiogram_dialog import BgManagerFactory
from dishka import AsyncContainer, make_async_container

from src.core.config import AppConfig

from .providers import get_providers


def create_container(config: AppConfig, bg_manager_factory: BgManagerFactory) -> AsyncContainer:
    context = {
        AppConfig: config,
        BgManagerFactory: bg_manager_factory,
    }

    container = make_async_container(*get_providers(), context=context)
    return container
