from aiogram_dialog import BgManagerFactory
from dishka import AsyncContainer, make_async_container

from src.core.config import AppConfig

from .providers import get_aiogram_providers, get_taskiq_providers


def create_aiogram_container(
    config: AppConfig, bg_manager_factory: BgManagerFactory
) -> AsyncContainer:
    context = {
        AppConfig: config,
        BgManagerFactory: bg_manager_factory,
    }
    return make_async_container(*get_aiogram_providers(), context=context)


def create_taskiq_container(
    config: AppConfig, bg_manager_factory: BgManagerFactory
) -> AsyncContainer:
    context = {
        AppConfig: config,
        BgManagerFactory: bg_manager_factory,
    }
    return make_async_container(*get_taskiq_providers(), context=context)
