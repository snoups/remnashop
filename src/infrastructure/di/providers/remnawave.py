from dishka import Provider, Scope, provide
from remnawave import RemnawaveSDK

from src.core.config import AppConfig


class RemnawaveProvider(Provider):
    scope = Scope.APP

    @provide
    def get_remnawave(self, config: AppConfig) -> RemnawaveSDK:
        return RemnawaveSDK(
            base_url=config.remnawave.url.get_secret_value(),
            token=config.remnawave.token.get_secret_value(),
        )
