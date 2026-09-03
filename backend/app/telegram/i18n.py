from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import AppConfig
from app.modules.settings import SettingsRepository, build_command_translator_hub
from app.modules.translations import TranslationsRepository
from app.modules.users import UserDto

if TYPE_CHECKING:
    from fluentogram import TranslatorHub, TranslatorRunner


async def read_translator_hub(config: AppConfig) -> "TranslatorHub":
    # Standalone engine, not the DI-managed one -- same rationale as
    # read_bot_settings() in app/modules/settings/bootstrap.py: this runs
    # before the process's dishka container exists.
    engine = create_async_engine(config.database.dsn)
    try:
        async with AsyncSession(engine) as session:
            active_locales = await SettingsRepository(session).list_active_locales()
            translations_by_locale = await TranslationsRepository(
                session
            ).get_fluent_text_by_locale(active_locales)
            return build_command_translator_hub(
                active_locales, translations_by_locale, config.default_locale
            )
    finally:
        await engine.dispose()


def get_translator(hub: "TranslatorHub", user: UserDto) -> "TranslatorRunner":
    return hub.get_translator_by_locale(user.language.value)
