from typing import Any, Final, Optional

import httpx
from fluent_compiler.bundle import FluentBundle
from loguru import logger

from app.core.enums import Locale
from app.modules.settings.bot_commands import BOT_COMMANDS
from app.modules.settings.dto import BotCommandDto
from app.modules.settings.telegram_status import TELEGRAM_API_URL

_TIMEOUT_SECONDS: Final[float] = 10.0
# outranks the default scope in private chats, so the pre-rebuild bot's
# commands set there would otherwise shadow ours
_PRIVATE_CHATS_SCOPE: Final[dict[str, str]] = {"type": "all_private_chats"}


async def push_bot_commands_to_telegram(
    token: Optional[str],
    proxy: Optional[str],
    commands: list[BotCommandDto],
    active_locales: list[Locale],
    translations_by_locale: dict[Locale, str],
    default_locale: Locale,
) -> bool:
    # Plain Bot API call and bare fluent_compiler bundles, not aiogram/fluentogram:
    # this runs in the api process too (every translation write re-pushes), and
    # those two live under the telegram extra.
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
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, proxy=proxy) as client:
            for lang in locales:
                payload: dict[str, Any] = {
                    "commands": [
                        {
                            "command": item.command,
                            "description": describe(
                                lang or default_locale.value,
                                by_command[item.command].description_key,
                            ),
                        }
                        for item in commands
                    ],
                    "scope": _PRIVATE_CHATS_SCOPE,
                }
                language: dict[str, Any] = {} if lang is None else {"language_code": lang}
                ok &= await _call(client, token, "setMyCommands", payload | language)
                # clears commands an older push left in the default scope,
                # which also shows them in groups
                ok &= await _call(client, token, "deleteMyCommands", language)
    except Exception:
        logger.exception("Failed to push bot commands to Telegram")
        return False
    return ok


async def delete_bot_commands_for_locale(token: str, proxy: Optional[str], locale: Locale) -> bool:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, proxy=proxy) as client:
            return await _call(
                client,
                token,
                "deleteMyCommands",
                {"scope": _PRIVATE_CHATS_SCOPE, "language_code": locale.value},
            )
    except Exception:
        logger.exception(f"Failed to delete bot commands for locale '{locale}'")
        return False


async def _call(
    client: httpx.AsyncClient, token: str, method: str, payload: dict[str, Any]
) -> bool:
    response = await client.post(f"{TELEGRAM_API_URL}/bot{token}/{method}", json=payload)
    body: dict[str, Any] = response.json()
    if body.get("ok"):
        return True
    logger.error(
        f"Telegram '{method}' failed for language "
        f"'{payload.get('language_code', 'default')}': {body.get('description')}"
    )
    return False
