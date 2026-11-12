import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.types import CallbackQuery, Chat, Message, Update, User
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.modules.settings import BotRequirementsDto
from app.modules.users import UserDto
from app.telegram.legal_gate import gate_message_key
from app.telegram.middlewares.requirements import channel_member_key
from app.telegram.routers.requirements.handlers import _resume, on_channel_check
from tests.fakes.aiogram_bot import FakeAiogramSession

_CHANNEL = BotRequirementsDto(channel_required=True, channel_id=-100, channel_url="https://t.me/x")
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


def _stored_plan_link() -> Message:
    return Message(
        message_id=5,
        date=datetime(2026, 10, 26, tzinfo=timezone.utc),
        chat=Chat(id=46, type="private"),
        from_user=User(id=46, is_bot=False, first_name="Ann"),
        text="/start plan_pro",
    )


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


async def _check(bot: _Bot, redis: Redis, dispatcher: Any = None) -> tuple[MagicMock, AsyncMock]:
    callback, _ = _callback(bot)
    dialog_manager = MagicMock(start=AsyncMock())
    await on_channel_check(
        callback,
        _USER,
        dialog_manager,
        _GetRequirements(_CHANNEL),  # type: ignore[arg-type]
        redis,
        _Hub(),  # type: ignore[arg-type]
        AsyncMock(),
        dispatcher or MagicMock(feed_update=AsyncMock()),
    )
    return callback, dialog_manager.start


async def test_channel_check_rechecks_past_the_cache(redis: Redis) -> None:
    assert _USER.telegram_id is not None
    await redis.set(channel_member_key(-100, _USER.telegram_id), "1")
    bot = _Bot("left")

    callback, start = await _check(bot, redis)

    assert bot.calls == 1
    callback.answer.assert_awaited_once_with("ntf-requirements.channel-not-found")
    start.assert_not_awaited()


async def test_channel_check_opens_the_menu_for_a_member(redis: Redis) -> None:
    callback, start = await _check(_Bot("member"), redis)

    callback.answer.assert_awaited_once_with()
    start.assert_awaited_once()


async def test_channel_check_replays_the_stopped_plan_link(redis: Redis) -> None:
    stored = _stored_plan_link()
    await redis.set(gate_message_key(_USER.id), stored.model_dump_json(), ex=60)
    dispatcher = MagicMock(feed_update=AsyncMock())

    _, start = await _check(_Bot("member"), redis, dispatcher)
    await asyncio.sleep(0)

    start.assert_not_awaited()
    assert dispatcher.feed_update.await_args.args[1].message.text == "/start plan_pro"
    assert await redis.get(gate_message_key(_USER.id)) is None


async def test_replay_runs_under_the_real_event_isolation(redis: Redis) -> None:
    # the callback holds the user's isolation lock; a replay awaited inside it
    # would wait on that lock forever
    stored = _stored_plan_link()
    await redis.set(gate_message_key(_USER.id), stored.model_dump_json(), ex=60)
    dispatcher = Dispatcher(storage=MemoryStorage(), events_isolation=SimpleEventIsolation())
    bot = Bot("42:TEST", session=FakeAiogramSession({"DeleteMessage": True}))
    replayed = asyncio.Event()

    @dispatcher.message()
    async def on_message(message: Message) -> None:
        replayed.set()

    @dispatcher.callback_query()
    async def on_callback(callback: CallbackQuery) -> None:
        await _resume(callback, _USER, MagicMock(start=AsyncMock()), redis, dispatcher)

    callback = CallbackQuery(
        id="1", from_user=stored.from_user, chat_instance="c", data="check", message=stored
    )
    try:
        await asyncio.wait_for(
            dispatcher.feed_update(bot, Update(update_id=1, callback_query=callback)), 5
        )
        await asyncio.wait_for(replayed.wait(), 5)
    finally:
        await bot.session.close()
