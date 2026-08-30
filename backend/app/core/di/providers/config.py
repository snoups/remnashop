from dishka import Provider, Scope, from_context

from app.core.config import AppConfig


class ConfigProvider(Provider):
    scope = Scope.APP

    config = from_context(provides=AppConfig)
