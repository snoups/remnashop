from datetime import datetime
from typing import Final, Optional

from fluent_compiler.bundle import FluentBundle
from fluentogram import FluentTranslator, TranslatorHub, TranslatorRunner
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import AppConfig
from app.core.enums import Locale
from app.modules.translations import TranslationRepository
from app.modules.users import UserDto

_EXPIRE_TIME_FORMAT: Final[str] = "%d.%m.%Y %H:%M"


def build_translator_hub(
    active_locales: list[Locale], translations_by_locale: dict[Locale, str], default_locale: Locale
) -> TranslatorHub:
    translators = [
        FluentTranslator(
            locale=locale.value,
            translator=FluentBundle.from_string(  # type: ignore[no-untyped-call]
                locale.value, text=translations_by_locale[locale]
            ),
        )
        for locale in active_locales
    ]
    return TranslatorHub(
        locales_map={locale.value: locale.value for locale in active_locales},
        translators=translators,
        root_locale=default_locale.value,
    )


async def read_translator_hub(config: AppConfig) -> TranslatorHub:
    # standalone engine, like read_bot_settings(): this runs before the
    # dishka container exists
    engine = create_async_engine(config.database.dsn)
    try:
        async with AsyncSession(engine) as session:
            translation_repository = TranslationRepository(session)
            active_locales = await translation_repository.list_active_locales()
            translations_by_locale = await translation_repository.get_fluent_text_by_locale(
                active_locales
            )
            default_locale = await translation_repository.get_default_locale()
            return build_translator_hub(active_locales, translations_by_locale, default_locale)
    finally:
        await engine.dispose()


def get_translator(hub: TranslatorHub, user: UserDto) -> TranslatorRunner:
    return hub.get_translator_by_locale(user.language.value)


def i18n_format_expire_time(expiry: Optional[datetime]) -> str:
    if expiry is None:
        return "—"
    return expiry.strftime(_EXPIRE_TIME_FORMAT)
