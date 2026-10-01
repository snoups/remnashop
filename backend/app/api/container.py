from dishka import AsyncContainer, make_async_container

from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.modules.providers import get_module_providers


def create_api_container(config: AppConfig) -> AsyncContainer:
    return make_async_container(
        *get_core_providers(), *get_module_providers(), context={AppConfig: config}
    )
