from typing import Any, Optional

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetChatMember
from aiogram.types import CallbackQuery, Chat, Message, User
from fluentogram import TranslatorHub
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.constants import CONTAINER_KEY, USER_KEY
from app.core.enums import LegalDocumentKind, Locale, Role
from app.core.utils.time import datetime_now
from app.modules.legal import (
    GetPendingLegalDocumentsUseCase,
    LegalRevisionDto,
    PendingLegalDocumentsDto,
)
from app.modules.settings import (
    BotRequirementsDto,
    BotStatusKind,
    GetBotRequirementsUseCase,
    ReportBotStatusDto,
    ReportBotStatusUseCase,
)
from app.modules.users import UserDto
from app.telegram.broadcast_callbacks import UNSUBSCRIBE_CALLBACK
from app.telegram.legal_gate import LegalAcceptCallback, LegalDocumentCallback, gate_message_key
from app.telegram.middlewares.requirements import CHANNEL_CHECK_CALLBACK, RequirementsMiddleware


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


class _GetPending:
    def __init__(self, pending: PendingLegalDocumentsDto) -> None:
        self._pending = pending

    async def execute(self, user: UserDto, channel: Any, locale: Any) -> PendingLegalDocumentsDto:
        return self._pending


_NOTHING_PENDING = PendingLegalDocumentsDto(documents=[], is_update=False)


class _Container:
    def __init__(
        self,
        requirements: BotRequirementsDto,
        redis: Redis,
        pending: PendingLegalDocumentsDto = _NOTHING_PENDING,
    ) -> None:
        self._requirements = requirements
        self._redis = redis
        self._pending = pending
        self.report = _Report()

    async def get(self, dependency_type: type) -> Any:
        if dependency_type is GetPendingLegalDocumentsUseCase:
            return _GetPending(self._pending)
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

    message = Message(
        message_id=1,
        date=datetime_now(),
        chat=Chat(id=9, type="private"),
        from_user=User(id=9, is_bot=False, first_name="Ann"),
        text="hi",
    )
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


async def test_staff_skip_requirements(redis: Redis) -> None:
    assert (
        await _run(
            _message([]), UserDto(id=1, name="a", role=Role.ADMIN), _CHANNEL, _Bot("left"), redis
        )
        is True
    )


async def test_requirement_callbacks_pass_through(redis: Redis) -> None:
    assert (
        await _run(
            _callback(CHANNEL_CHECK_CALLBACK),
            UserDto(id=1, name="c"),
            _CHANNEL,
            _Bot("left"),
            redis,
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
    assert (
        await _run(message, UserDto(id=1, name="c", telegram_id=47), _CHANNEL, _Bot("left"), redis)
        is True
    )


async def test_failed_report_still_lets_customers_through(redis: Redis) -> None:
    user = UserDto(id=1, name="c", telegram_id=45)
    container = _Container(_CHANNEL, redis)

    async def boom(data: ReportBotStatusDto) -> None:
        raise ConnectionError("db down")

    container.report.system = boom  # type: ignore[method-assign]

    assert await _run(_message([]), user, _CHANNEL, _Bot(None), redis, container) is True


def _agreement(revision_id: int = 1) -> LegalRevisionDto:
    return LegalRevisionDto(
        id=revision_id,
        kind=LegalDocumentKind.USER_AGREEMENT,
        locale=Locale.RU,
        channel=None,
        title="t",
        body="b",
        created_at=datetime_now(),
    )


_NEW = PendingLegalDocumentsDto(documents=[_agreement()], is_update=False)
_UPDATED = PendingLegalDocumentsDto(documents=[_agreement()], is_update=True)
_NONE = BotRequirementsDto()


async def test_gate_blocks_until_accepted(redis: Redis) -> None:
    answered: list[Any] = []
    container = _Container(_NONE, redis, _NEW)

    called = await _run(
        _message(answered), UserDto(id=1, name="c"), _NONE, _Bot("member"), redis, container
    )

    assert called is False
    assert answered == ["msg-legal-gate"]


async def test_gate_shows_update_text(redis: Redis) -> None:
    answered: list[Any] = []
    container = _Container(_NONE, redis, _UPDATED)

    await _run(_message(answered), UserDto(id=1, name="c"), _NONE, _Bot("member"), redis, container)

    assert answered == ["msg-legal-gate-update"]


async def test_no_pending_documents_passes_to_channel_check(redis: Redis) -> None:
    answered: list[Any] = []
    user = UserDto(id=1, name="c", telegram_id=48)

    assert await _run(_message(answered), user, _CHANNEL, _Bot("left"), redis) is False
    assert answered == ["ntf-requirements.channel"]


@pytest.mark.parametrize(
    "data",
    [
        LegalDocumentCallback(kind=LegalDocumentKind.USER_AGREEMENT).pack(),
        LegalAcceptCallback(ids="1").pack(),
        UNSUBSCRIBE_CALLBACK,
    ],
)
async def test_gate_lets_document_and_unsubscribe_callbacks_through(
    redis: Redis, data: str
) -> None:
    container = _Container(_NONE, redis, _NEW)

    assert (
        await _run(
            _callback(data), UserDto(id=1, name="c"), _NONE, _Bot("member"), redis, container
        )
        is True
    )


async def test_privileged_and_payment_bypass_gate(redis: Redis) -> None:
    container = _Container(_NONE, redis, _NEW)
    staff = UserDto(id=1, name="a", role=Role.ADMIN)
    payment = _message([])
    object.__setattr__(payment, "successful_payment", object())

    assert await _run(_message([]), staff, _NONE, _Bot("member"), redis, container) is True
    assert await _run(payment, UserDto(id=2, name="c"), _NONE, _Bot("member"), redis, container)


def test_accept_callback_fits_64_bytes() -> None:
    assert len(LegalAcceptCallback(ids="999999999,999999999").pack().encode()) <= 64


async def test_gate_remembers_the_stopped_message(redis: Redis) -> None:
    message = _message([])
    object.__setattr__(message, "text", "/start webauth_abc")
    container = _Container(_NONE, redis, _NEW)

    await _run(message, UserDto(id=31, name="c"), _NONE, _Bot("member"), redis, container)

    stored = await redis.get(gate_message_key(31))
    assert stored is not None and "webauth_abc" in stored
