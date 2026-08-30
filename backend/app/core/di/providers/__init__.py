from dishka import Provider

from app.core.di.providers.config import ConfigProvider
from app.core.di.providers.database import DatabaseProvider
from app.core.di.providers.event_bus import EventBusProvider
from app.core.di.providers.redis import RedisProvider
from app.core.di.providers.remnawave import RemnawaveProvider

__all__ = [
    "ConfigProvider",
    "DatabaseProvider",
    "EventBusProvider",
    "RedisProvider",
    "RemnawaveProvider",
    "get_core_providers",
]


def get_core_providers() -> list[Provider]:
    return [
        ConfigProvider(),
        DatabaseProvider(),
        RedisProvider(),
        EventBusProvider(),
        RemnawaveProvider(),
    ]
