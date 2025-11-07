from typing import Optional

from dishka import Provider, Scope, provide
from dishka.integrations.aiogram import AiogramMiddlewareData
from fluentogram import TranslatorHub, TranslatorRunner
from fluentogram.storage import FileStorage
from loguru import logger

from src.core.config import AppConfig
from src.core.constants import USER_KEY
from src.infrastructure.database.models.dto import UserDto


class I18nProvider(Provider):
    scope = Scope.APP

    @provide
    def get_hub(self, config: AppConfig) -> TranslatorHub:
        storage = FileStorage(path=config.translations_dir / "{locale}")
        locales_map: dict[str, tuple[str, ...]] = {}

        for locale_code in config.locales:
            fallback_chain: list[str] = [locale_code]
            if config.default_locale != locale_code:
                fallback_chain.append(config.default_locale)
            locales_map[locale_code] = tuple(fallback_chain)

        if config.default_locale not in locales_map:
            locales_map[config.default_locale] = tuple(
                config.default_locale,
            )

        logger.debug(
            f"Loaded TranslatorHub with locales: "
            f"{[locale.value for locale in locales_map.keys()]}, "  # type: ignore[attr-defined]
            f"default={config.default_locale.value}"
        )

        return TranslatorHub(locales_map, root_locale=config.default_locale, storage=storage)

    @provide(scope=Scope.REQUEST)
    def get_translator(
        self,
        config: AppConfig,
        hub: TranslatorHub,
        middleware_data: AiogramMiddlewareData,
    ) -> TranslatorRunner:
        user: Optional[UserDto] = middleware_data.get(USER_KEY)

        if user:
            logger.debug(f"Translator for user '{user.telegram_id}' with locale={user.language}")
            return hub.get_translator_by_locale(locale=user.language)

        else:
            logger.debug(
                f"Translator for anonymous user with default locale={config.default_locale}"
            )
            return hub.get_translator_by_locale(locale=config.default_locale)
