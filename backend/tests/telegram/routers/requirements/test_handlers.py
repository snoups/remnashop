from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.modules.settings import BotRequirementsDto
from app.modules.users import UserDto
from app.telegram.middlewares.requirements import CHANNEL_CHECK_CALLBACK, channel_member_key
from app.telegram.routers.requirements.handlers import on_channel_check, on_rules_accepted

_CHANNEL = BotRequirementsDto(
    rules_required=True,
    rules_url="https://example.com/rules",
    channel_required=True,
    channel_id=-100,
    channel_url="https://t.me/x",
)
_NO_CHANNEL = BotRequirementsDto(rules_required=True, rules_url="https://example.com/rules")
_USER = UserDto(id=1, name="c", telegram_id=46)


class _Hub:
    def get_translator_by_locale(self, locale: str) -> Any:
        return MagicMock(get=lambda key, **kwargs: key)


class _GetRequirements:
    def __init__(self, requirements: BotRequirementsDto) -> None:
        self._requirements = requirements

    @property
    def system(self) -> "_GetRequirements":
        return self

    async def __call__(self) -> BotRequirementsDto:
        return self._requirements


class _Bot:
    def __init__(self, status: str) -> None:
        self.status = status
        self.calls = 0

    async def get_chat_member(self, chat_id: int, user_id: int) -> Any:
        self.calls += 1
        return type("Member", (), {"status": self.status})()


def _callback(bot: _Bot) -> tuple[CallbackQuery, MagicMock]:
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    message.delete = AsyncMock()
    callback = MagicMock(spec=CallbackQuery)
    callback.bot = bot
    callback.message = message
    callback.answer = AsyncMock()
    return callback, message


@pytest.fixture
async def redis(config: AppConfig) -> Any:
    client = Redis.from_url(config.redis.dsn, decode_responses=True)
    yield client
    await client.aclose()


async def _accept(
    bot: _Bot, requirements: BotRequirementsDto, redis: Redis
) -> tuple[MagicMock, AsyncMock]:
    callback, message = _callback(bot)
    dialog_manager = MagicMock(start=AsyncMock())
    accept_rules = AsyncMock()
    await on_rules_accepted(
        callback,
        _USER,
        dialog_manager,
        accept_rules,
        _GetRequirements(requirements),  # type: ignore[arg-type]
        redis,
        _Hub(),  # type: ignore[arg-type]
    )
    accept_rules.assert_awaited_once_with(_USER)
    return message, dialog_manager.start


async def test_accepting_rules_moves_on_to_the_channel_step(redis: Redis) -> None:
    message, start = await _accept(_Bot("left"), _CHANNEL, redis)

    start.assert_not_awaited()
    text = message.answer.await_args.args[0]
    keyboard = message.answer.await_args.kwargs["reply_markup"]
    assert text == "ntf-requirements.channel"
    assert keyboard.inline_keyboard[1][0].callback_data == CHANNEL_CHECK_CALLBACK


async def test_accepting_rules_opens_the_menu_for_a_subscriber(redis: Redis) -> None:
    message, start = await _accept(_Bot("member"), _CHANNEL, redis)

    start.assert_awaited_once()
    message.answer.assert_not_awaited()


async def test_accepting_rules_opens_the_menu_without_a_channel_requirement(
    redis: Redis,
) -> None:
    bot = _Bot("left")
    _, start = await _accept(bot, _NO_CHANNEL, redis)

    start.assert_awaited_once()
    assert bot.calls == 0


async def _check(bot: _Bot, redis: Redis) -> tuple[MagicMock, AsyncMock]:
    callback, _ = _callback(bot)
    dialog_manager = MagicMock(start=AsyncMock())
    await on_channel_check(
        callback,
        _USER,
        dialog_manager,
        _GetRequirements(_CHANNEL),  # type: ignore[arg-type]
        redis,
        _Hub(),  # type: ignore[arg-type]
    )
    return callback, dialog_manager.start


async def test_channel_check_rechecks_past_the_cache(redis: Redis) -> None:
    assert _USER.telegram_id is not None
    await redis.set(channel_member_key(-100, _USER.telegram_id), "1")
    bot = _Bot("left")

    callback, start = await _check(bot, redis)

    assert bot.calls == 1
    callback.answer.assert_awaited_once_with("ntf-requirements.channel-not-found", show_alert=True)
    start.assert_not_awaited()


async def test_channel_check_opens_the_menu_for_a_member(redis: Redis) -> None:
    callback, start = await _check(_Bot("member"), redis)

    callback.answer.assert_awaited_once_with()
    start.assert_awaited_once()
