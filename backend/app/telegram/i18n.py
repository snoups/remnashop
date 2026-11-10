from datetime import datetime
from decimal import Decimal
from typing import Final, Optional

from fluent_compiler.bundle import FluentBundle
from fluentogram import FluentTranslator, TranslatorHub, TranslatorRunner

from app.core.config import AppConfig
from app.core.db.standalone import standalone_session
from app.core.enums import Locale
from app.modules.translations import TranslationRepository
from app.modules.users import UserDto

_DATETIME_FORMAT: Final[str] = "%d.%m.%Y %H:%M"
_DATE_FORMAT: Final[str] = "%d.%m.%Y"


def build_translator_hub(
    active_locales: list[Locale], translations_by_locale: dict[Locale, str], default_locale: Locale
) -> TranslatorHub:
    translators = [
        FluentTranslator(
            locale=locale.value,
            # bidi marks around a placeable on its own line show up in Telegram
            # as an empty line, e.g. before a select's <blockquote>
            translator=FluentBundle.from_string(  # type: ignore[no-untyped-call]
                locale.value, text=translations_by_locale[locale], use_isolating=False
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
    # runs before the dishka container exists
    async with standalone_session(config) as session:
        translation_repository = TranslationRepository(session)
        active_locales = await translation_repository.list_active_locales()
        translations_by_locale = await translation_repository.get_fluent_text_by_locale(
            active_locales
        )
        default_locale = await translation_repository.get_default_locale()
        return build_translator_hub(active_locales, translations_by_locale, default_locale)


def telegram_locale(hub: TranslatorHub, language_code: Optional[str]) -> Optional[Locale]:
    # "pt-br" -> "pt"; only a locale the bot actually serves counts
    code = (language_code or "").split("-")[0].lower()
    return Locale(code) if code in hub.translators_map else None


def get_translator(hub: TranslatorHub, user: UserDto) -> TranslatorRunner:
    return hub.get_translator_by_locale(user.language.value)


# every date the bot shows a customer goes through these two
def format_datetime(value: Optional[datetime]) -> str:
    return value.strftime(_DATETIME_FORMAT) if value is not None else "—"


def format_date(value: Optional[datetime]) -> str:
    return value.strftime(_DATE_FORMAT) if value is not None else "—"


def format_price(price: Decimal) -> str:
    return f"{price:.2f}".removesuffix(".00")
