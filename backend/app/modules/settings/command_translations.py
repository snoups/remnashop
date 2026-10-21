from collections.abc import Awaitable
from typing import Final, Optional

from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats
from fluent_compiler.bundle import FluentBundle
from loguru import logger

from app.core.enums import Locale
from app.core.telegram_api import bot_client
from app.modules.settings.bot_commands import BOT_COMMANDS
from app.modules.settings.dto import BotCommandDto

_TIMEOUT_SECONDS: Final[float] = 10.0
# outranks the default scope in private chats, so commands set there earlier
# would otherwise shadow ours
_PRIVATE_CHATS_SCOPE: Final[BotCommandScopeAllPrivateChats] = BotCommandScopeAllPrivateChats()


async def push_bot_commands_to_telegram(
    token: Optional[str],
    proxy: Optional[str],
    commands: list[BotCommandDto],
    active_locales: list[Locale],
    translations_by_locale: dict[Locale, str],
    default_locale: Locale,
) -> bool:
    # bare fluent_compiler bundles, not fluentogram: this runs in the api process
    # too (every translation write re-pushes), and fluentogram lives under the
    # telegram extra
    assert token is not None
    by_command = {item.command: item for item in BOT_COMMANDS}
    locales: list[Optional[str]] = [locale.value for locale in active_locales] + [None]

    try:
        bundles = {
            locale.value: FluentBundle.from_string(  # type: ignore[no-untyped-call]
                locale.value, text=translations_by_locale[locale]
            )
            for locale in active_locales
        }

        def describe(lang: str, key: str) -> str:
            # a missing key raises KeyError, same as fluentogram's lookup failing
            text, errors = bundles[lang].format(key, {})
            if errors:
                raise errors[0]
            return str(text)

        ok = True
        async with bot_client(token, proxy, timeout=_TIMEOUT_SECONDS) as bot:
            for lang in locales:
                bot_commands = [
                    BotCommand(
                        command=item.command,
                        description=describe(
                            lang or default_locale.value, by_command[item.command].description_key
                        ),
                    )
                    for item in commands
                ]
                ok &= await _accepted(
                    bot.set_my_commands(
                        commands=bot_commands, scope=_PRIVATE_CHATS_SCOPE, language_code=lang
                    ),
                    "setMyCommands",
                    lang,
                )
                # clears commands an older push left in the default scope,
                # which also shows them in groups
                ok &= await _accepted(
                    bot.delete_my_commands(language_code=lang), "deleteMyCommands", lang
                )
    except Exception:
        logger.exception("Failed to push bot commands to Telegram")
        return False
    return ok


async def delete_bot_commands_for_locale(token: str, proxy: Optional[str], locale: Locale) -> bool:
    try:
        async with bot_client(token, proxy, timeout=_TIMEOUT_SECONDS) as bot:
            return await _accepted(
                bot.delete_my_commands(scope=_PRIVATE_CHATS_SCOPE, language_code=locale.value),
                "deleteMyCommands",
                locale.value,
            )
    except Exception:
        logger.exception(f"Failed to delete bot commands for locale '{locale}'")
        return False


async def _accepted(call: Awaitable[bool], method: str, lang: Optional[str]) -> bool:
    # Telegram refusing one language doesn't stop the others; a network failure does
    try:
        return await call
    except TelegramNetworkError:
        raise
    except TelegramAPIError as error:
        logger.error(
            f"Telegram '{method}' failed for language '{lang or 'default'}': {error.message}"
        )
        return False
