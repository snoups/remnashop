from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import AppConfig
from app.core.db.models.active_locale import ActiveLocale
from app.core.db.models.bot_translation import BotTranslation
from app.core.enums import Locale, Role
from app.modules.settings.repository import SettingsRepository
from app.modules.translations.repository import TranslationRepository
from app.modules.users.dto import UserDto
from app.telegram.i18n import get_translator, read_translator_hub

_MESSAGE_ID = "test_i18n_hub_check"


async def test_read_translator_hub_builds_a_working_hub(config: AppConfig) -> None:
    # read_translator_hub opens its own engine, so the seed goes through a
    # separate committed connection; the rolled-back `session` is invisible to it
    locale = Locale.EN
    engine = create_async_engine(config.database.dsn)
    added_locale = False
    try:
        async with AsyncSession(engine, expire_on_commit=False) as seed_session:
            settings_repository = SettingsRepository(seed_session)
            if (
                locale
                not in await TranslationRepository(
                    settings_repository.session
                ).list_active_locales()
            ):
                await TranslationRepository(settings_repository.session).add_active_locale(locale)
                added_locale = True
            await TranslationRepository(seed_session).seed_missing(locale, _MESSAGE_ID, "", "ok")
            await seed_session.commit()

        hub = await read_translator_hub(config)
        runner = hub.get_translator_by_locale(locale.value)
        assert runner is not None
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(BotTranslation).where(
                    BotTranslation.locale == locale, BotTranslation.message_id == _MESSAGE_ID
                )
            )
            if added_locale:
                await connection.execute(delete(ActiveLocale).where(ActiveLocale.locale == locale))
        await engine.dispose()


def test_get_translator_resolves_by_user_language() -> None:
    class _FakeHub:
        def get_translator_by_locale(self, locale: str) -> str:
            return locale

    user = UserDto(id=1, name="test", role=Role.USER, language=Locale.RU)
    result = get_translator(_FakeHub(), user)  # type: ignore[arg-type]
    assert result == "ru"
