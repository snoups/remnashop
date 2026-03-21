from typing import Optional

from adaptix import Retort
from dishka import AnyOf, Provider, Scope, provide
from dishka.integrations.aiogram import AiogramMiddlewareData
from fluentogram.storage import FileStorage
from loguru import logger

from src.application.common import TranslatorHub as TranslatorHubProtocol
from src.application.common import TranslatorRunner as TranslatorRunnerProtocol
from src.application.dto import UserDto
from src.core.config import AppConfig
from src.core.constants import USER_KEY
from src.infrastructure.services import TranslatorHubImpl


class I18nProvider(Provider):
    scope = Scope.APP

    @provide
    def get_translator_hub(
        self,
        config: AppConfig,
        retort: Retort,
    ) -> AnyOf[TranslatorHubProtocol, TranslatorHubImpl]:
        storage = FileStorage(path=config.translations_dir / "{locale}")
        locales_map: dict[str, tuple[str, ...]] = {}

        for locale_code in config.locales:
            fallback_chain: list[str] = [locale_code]
            if config.default_locale != locale_code:
                fallback_chain.append(config.default_locale)
            locales_map[locale_code] = tuple(fallback_chain)

        if config.default_locale not in locales_map:
            locales_map[config.default_locale] = (config.default_locale,)

        logger.debug(
            f"Loaded TranslatorHub with locales: "
            f"{[locale.value for locale in locales_map.keys()]}, "  # type: ignore[attr-defined]
            f"default={config.default_locale.value}"
        )

        return TranslatorHubImpl(
            locales_map,
            root_locale=config.default_locale,
            storage=storage,
            retort=retort,
        )


class I18nAiogramProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def get_translator(
        self,
        config: AppConfig,
        translator_hub: TranslatorHubProtocol,
        middleware_data: AiogramMiddlewareData,
    ) -> TranslatorRunnerProtocol:
        user: Optional[UserDto] = middleware_data.get(USER_KEY)
        locale = user.language if user else config.default_locale
        return translator_hub.get_translator_by_locale(locale=locale)


class I18nTaskiqProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def get_translator(
        self,
        config: AppConfig,
        translator_hub: TranslatorHubProtocol,
    ) -> TranslatorRunnerProtocol:
        return translator_hub.get_translator_by_locale(locale=config.default_locale)
