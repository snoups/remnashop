from typing import TYPE_CHECKING, Any, Final, Optional

import httpx
from fluent_compiler.bundle import FluentBundle
from loguru import logger

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.modules.settings.bot_commands import BOT_COMMANDS
from app.modules.settings.dto import BotCommandDto
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.telegram_status import TELEGRAM_API_URL

if TYPE_CHECKING:
    from fluentogram import TranslatorHub

    from app.modules.translations import TranslationsRepository

_TIMEOUT_SECONDS: Final[float] = 10.0
# outranks the default scope in private chats, so the pre-rebuild bot's
# commands set there would otherwise shadow ours
_PRIVATE_CHATS_SCOPE: Final[dict[str, str]] = {"type": "all_private_chats"}


def build_command_translator_hub(
    active_locales: list[Locale], translations_by_locale: dict[Locale, str], default_locale: Locale
) -> "TranslatorHub":
    # Lazy import -- fluentogram lives under the `telegram` extra; only the
    # bot process builds a hub.
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
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
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


async def delete_bot_commands_for_locale(token: str, locale: Locale) -> bool:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
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


async def repush_bot_commands_if_configured(
    settings_repository: SettingsRepository,
    translations_repository: "TranslationsRepository",
    config: AppConfig,
    uow: UnitOfWork,
) -> bool:
    async with uow:
        bot_settings = await settings_repository.get_bot_settings()
    if not bot_settings.is_configured:
        return True

    # Lazy import -- usecases import this module, so a top-level import is circular.
    from app.modules.settings.usecases.get_bot_commands import (  # noqa: PLC0415
        GetBotCommandsUseCase,
    )

    commands = await GetBotCommandsUseCase(settings_repository, uow).system()
    enabled = [item for item in commands if item.enabled]
    async with uow:
        active_locales = await settings_repository.list_active_locales()
        translations_by_locale = await translations_repository.get_fluent_text_by_locale(
            active_locales
        )
    token = bot_settings.token.get_secret_value() if bot_settings.token is not None else None
    return await push_bot_commands_to_telegram(
        token,
        enabled,
        active_locales,
        translations_by_locale,
        config.default_locale,
    )
