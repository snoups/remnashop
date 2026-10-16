from typing import Any, Optional

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetChatMember
from aiogram.types import CallbackQuery, Message
from fluentogram import TranslatorHub
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.constants import CONTAINER_KEY, USER_KEY
from app.core.enums import Role
from app.core.utils.time import datetime_now
from app.modules.settings import (
    BotRequirementsDto,
    BotStatusKind,
    GetBotRequirementsUseCase,
    ReportBotStatusDto,
    ReportBotStatusUseCase,
)
from app.modules.users import UserDto
from app.telegram.middlewares.requirements import RULES_ACCEPT_CALLBACK, RequirementsMiddleware


class _Runner:
    def get(self, key: str, **kwargs: Any) -> str:
        return key


class _Hub:
    def get_translator_by_locale(self, locale: str) -> _Runner:
        return _Runner()


class _GetRequirements:
    def __init__(self, requirements: BotRequirementsDto) -> None:
        self._requirements = requirements

    @property
    def system(self) -> "_GetRequirements":
        return self

    async def __call__(self) -> BotRequirementsDto:
        return self._requirements


class _Report:
    def __init__(self) -> None:
        self.reports: list[ReportBotStatusDto] = []

    async def system(self, data: ReportBotStatusDto) -> None:
        self.reports.append(data)


class _Container:
    def __init__(self, requirements: BotRequirementsDto, redis: Redis) -> None:
        self._requirements = requirements
        self._redis = redis
        self.report = _Report()

    async def get(self, dependency_type: type) -> Any:
        if dependency_type is TranslatorHub:
            return _Hub()
        if dependency_type is Redis:
            return self._redis
        if dependency_type is ReportBotStatusUseCase:
            return self.report
        assert dependency_type is GetBotRequirementsUseCase
        return _GetRequirements(self._requirements)


class _Bot:
    def __init__(self, status: Optional[str]) -> None:
        self._status = status  # None -> Telegram API error
        self.calls = 0

    async def get_chat_member(self, chat_id: int, user_id: int) -> Any:
        self.calls += 1
        if self._status is None:
            raise TelegramBadRequest(
                method=GetChatMember(chat_id=chat_id, user_id=user_id), message="chat not found"
            )
        return type("Member", (), {"status": self._status})()


def _message(answered: list[Any]) -> Message:
    async def _answer(text: str, **kwargs: Any) -> None:
        answered.append(text)

    message = object.__new__(Message)
    object.__setattr__(message, "successful_payment", None)
    object.__setattr__(message, "answer", _answer)
    return message


def _callback(data: str) -> CallbackQuery:
    callback = object.__new__(CallbackQuery)
    object.__setattr__(callback, "data", data)
    return callback


@pytest.fixture
async def redis(config: AppConfig) -> Any:
    client = Redis.from_url(config.redis.dsn, decode_responses=True)
    yield client
    await client.aclose()


_RULES = BotRequirementsDto(rules_required=True, rules_url="https://example.com/rules")
_CHANNEL = BotRequirementsDto(channel_required=True, channel_id=-100, channel_url="https://t.me/x")


async def _run(
    event: Any,
    user: UserDto,
    requirements: BotRequirementsDto,
    bot: _Bot,
    redis: Redis,
    container: Optional[_Container] = None,
) -> bool:
    called = False

    async def handler(e: Any, d: dict[str, Any]) -> None:
        nonlocal called
        called = True

    container = container or _Container(requirements, redis)
    data = {USER_KEY: user, CONTAINER_KEY: container, "bot": bot}
    await RequirementsMiddleware().middleware_logic(handler, event, data)
    return called


async def test_unaccepted_rules_stop_the_customer(redis: Redis) -> None:
    answered: list[Any] = []
    assert (
        await _run(_message(answered), UserDto(id=1, name="c"), _RULES, _Bot("member"), redis)
        is False
    )
    assert answered == ["ntf-requirements.rules"]


async def test_accepted_rules_pass(redis: Redis) -> None:
    user = UserDto(id=1, name="c", rules_accepted_at=datetime_now())
    assert await _run(_message([]), user, _RULES, _Bot("member"), redis) is True


async def test_staff_skip_requirements(redis: Redis) -> None:
    assert (
        await _run(
            _message([]), UserDto(id=1, name="a", role=Role.ADMIN), _RULES, _Bot("left"), redis
        )
        is True
    )


async def test_requirement_callbacks_pass_through(redis: Redis) -> None:
    assert (
        await _run(
            _callback(RULES_ACCEPT_CALLBACK), UserDto(id=1, name="c"), _RULES, _Bot("left"), redis
        )
        is True
    )


async def test_unsubscribed_customer_is_stopped_and_not_cached(redis: Redis) -> None:
    bot = _Bot("left")
    user = UserDto(id=1, name="c", telegram_id=42)
    assert await _run(_message([]), user, _CHANNEL, bot, redis) is False
    assert await _run(_message([]), user, _CHANNEL, bot, redis) is False
    assert bot.calls == 2


async def test_subscription_is_cached(redis: Redis) -> None:
    bot = _Bot("member")
    user = UserDto(id=1, name="c", telegram_id=43)
    assert await _run(_message([]), user, _CHANNEL, bot, redis) is True
    assert await _run(_message([]), user, _CHANNEL, bot, redis) is True
    assert bot.calls == 1


async def test_broken_channel_setup_lets_customers_through(redis: Redis) -> None:
    user = UserDto(id=1, name="c", telegram_id=44)
    container = _Container(_CHANNEL, redis)

    assert await _run(_message([]), user, _CHANNEL, _Bot(None), redis, container) is True

    assert [(r.kind, r.channel_id) for r in container.report.reports] == [
        (BotStatusKind.CHANNEL_CHECK_FAILED, -100)
    ]


async def test_membership_is_cached_per_channel(redis: Redis) -> None:
    bot = _Bot("member")
    user = UserDto(id=1, name="c", telegram_id=45)
    other = BotRequirementsDto(channel_required=True, channel_id=-200, channel_url="https://t.me/y")
    assert await _run(_message([]), user, _CHANNEL, bot, redis) is True
    assert await _run(_message([]), user, other, bot, redis) is True
    assert bot.calls == 2


async def test_successful_payment_passes_unmet_requirements(redis: Redis) -> None:
    message = _message([])
    object.__setattr__(message, "successful_payment", object())
    assert await _run(message, UserDto(id=1, name="c"), _RULES, _Bot("member"), redis) is True


async def test_failed_report_still_lets_customers_through(redis: Redis) -> None:
    user = UserDto(id=1, name="c", telegram_id=45)
    container = _Container(_CHANNEL, redis)

    async def boom(data: ReportBotStatusDto) -> None:
        raise ConnectionError("db down")

    container.report.system = boom  # type: ignore[method-assign]

    assert await _run(_message([]), user, _CHANNEL, _Bot(None), redis, container) is True
