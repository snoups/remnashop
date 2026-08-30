from typing import TYPE_CHECKING, Optional

from loguru import logger

from app.core.enums import Locale
from app.modules.settings.bot_commands import BOT_COMMANDS
from app.modules.settings.dto import BotCommandDto

if TYPE_CHECKING:
    from fluentogram import TranslatorHub


def build_command_translator_hub(
    active_locales: list[Locale], translations_by_locale: dict[Locale, str], default_locale: Locale
) -> "TranslatorHub":
    # Lazy import -- fluentogram/fluent_compiler live under the `telegram`
    # extra, not base deps; this must not load on every api-process import.
    from fluent_compiler.bundle import FluentBundle  # noqa: PLC0415
    from fluentogram import FluentTranslator  # noqa: PLC0415
    from fluentogram import TranslatorHub as FluentogramTranslatorHub  # noqa: PLC0415

    translators = [
        FluentTranslator(
            locale=locale.value,
            translator=FluentBundle.from_string(  # type: ignore[no-untyped-call]
                locale.value, text=translations_by_locale[locale]
            ),
        )
        for locale in active_locales
    ]
    return FluentogramTranslatorHub(
        locales_map={locale.value: locale.value for locale in active_locales},
        translators=translators,
        root_locale=default_locale.value,
    )


async def push_bot_commands_to_telegram(
    token: Optional[str],
    commands: list[BotCommandDto],
    active_locales: list[Locale],
    translations_by_locale: dict[Locale, str],
    default_locale: Locale,
) -> bool:
    # Lazy import -- aiogram (+aiohttp) costs ~85MB RSS; only this rare admin
    # action needs it, not every process that imports this module.
    from aiogram import Bot  # noqa: PLC0415
    from aiogram.types import BotCommand as AiogramBotCommand  # noqa: PLC0415

    assert token is not None
    by_command = {item.command: item for item in BOT_COMMANDS}
    hub = build_command_translator_hub(active_locales, translations_by_locale, default_locale)
    locales: list[Optional[str]] = [locale.value for locale in active_locales] + [None]

    bot = Bot(token=token)
    try:
        for lang in locales:
            runner = hub.get_translator_by_locale(lang or default_locale.value)
            aiogram_commands = [
                AiogramBotCommand(
                    command=item.command,
                    description=runner.get(by_command[item.command].description_key),
                )
                for item in commands
            ]

            success = await bot.set_my_commands(commands=aiogram_commands, language_code=lang)
            if not success:
                return False
    except Exception:
        logger.exception("Failed to push bot commands to Telegram")
        return False
    finally:
        await bot.session.close()
    return True
