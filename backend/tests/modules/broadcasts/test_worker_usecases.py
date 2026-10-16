import asyncio
import json
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from redis.asyncio.lock import Lock
from redis.exceptions import LockNotOwnedError
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.constants import REDIS_KEY_PREFIX
from app.core.db.models.broadcast import Broadcast, BroadcastRecipient
from app.core.db.models.promocode import Promocode
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    BroadcastButtonKind,
    BroadcastChannel,
    BroadcastDelivery,
    BroadcastMediaType,
    BroadcastRecipientStatus,
    BroadcastStatus,
    Locale,
    PromocodeRewardType,
)
from app.core.error_codes import ErrorCode
from app.core.events import BaseEvent
from app.core.exceptions import ConflictError
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dto import (
    BroadcastAudienceDto,
    BroadcastButtonDto,
    BroadcastContentDto,
    BroadcastDto,
    BroadcastEmailContentDto,
)
from app.modules.broadcasts.events import (
    BroadcastCompletedEvent,
    BroadcastFailedEvent,
    BroadcastStartedEvent,
)
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.storage import media_path
from app.modules.broadcasts.telegram_api import get_bot_username
from app.modules.broadcasts.usecases import (
    DeliverBroadcastBatchUseCase,
    GetBroadcastUseCase,
    PruneBroadcastRecipientsUseCase,
    RecallBroadcastBatchUseCase,
    RecallBroadcastUseCase,
    RetryBroadcastUseCase,
    StartBroadcastUseCase,
    TickBroadcastsUseCase,
)
from app.modules.broadcasts.usecases import deliver_broadcast_batch as deliver_module
from app.modules.broadcasts.usecases import recall_broadcast_batch as recall_module
from app.modules.promocodes.dto import CreatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.settings.dto import UpdateBotRequirementsDto, UpdateBotSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.translations.repository import TranslationRepository
from app.modules.users.events import BotBlockedByUserEvent
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.broadcasts.factories import MockTelegram, make_customer, ok_response
from tests.modules.broadcasts.test_repository import save_dto

Responder = Callable[[httpx.Request], httpx.Response]


def _store_jpeg(media_dir: Path, broadcast_id: int) -> None:
    path = media_path(media_dir, broadcast_id, 0, "jpg")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"jpeg")


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[BaseEvent] = []

    async def publish(self, event: BaseEvent) -> None:
        self.events.append(event)


def _strip(event: BaseEvent) -> dict[str, object]:
    fields = {k: v for k, v in vars(event).items() if k not in ("event_id", "occurred_at")}
    return {"type": type(event).__name__, **fields}


def _published(publisher: RecordingPublisher) -> list[dict[str, object]]:
    return [_strip(e) for e in publisher.events]


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deliver_module, "GROUP_PAUSE_S", 0)
    monkeypatch.setattr(recall_module, "GROUP_PAUSE_S", 0)


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
def start_dispatch() -> RecordingDispatch:
    return RecordingDispatch()


@pytest.fixture
def deliver_dispatch() -> RecordingDispatch:
    return RecordingDispatch()


@pytest.fixture
def recall_dispatch() -> RecordingDispatch:
    return RecordingDispatch()


@pytest.fixture
def email_dispatch() -> RecordingDispatch:
    return RecordingDispatch()


@pytest.fixture
def media_config(config: AppConfig, tmp_path: Path) -> AppConfig:
    return config.model_copy(update={"media_dir": tmp_path})


@pytest.fixture
async def with_token(settings_repository: SettingsRepository) -> None:
    await settings_repository.update_bot_settings(UpdateBotSettingsDto(token="123:abc"))


@pytest.fixture
def make_start(
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    promocode_repository: PromocodeRepository,
    media_config: AppConfig,
    deliver_dispatch: RecordingDispatch,
    email_dispatch: RecordingDispatch,
    uow: UnitOfWork,
    publisher: RecordingPublisher,
) -> Callable[[MockTelegram], StartBroadcastUseCase]:
    def build(telegram: MockTelegram) -> StartBroadcastUseCase:
        return StartBroadcastUseCase(
            broadcast_repository,
            settings_repository,
            promocode_repository,
            telegram,
            media_config,
            deliver_dispatch,
            email_dispatch,
            uow,
            publisher,
        )

    return build


@pytest.fixture
def make_deliver(
    broadcast_repository: BroadcastRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    promocode_repository: PromocodeRepository,
    translation_repository: TranslationRepository,
    media_config: AppConfig,
    deliver_dispatch: RecordingDispatch,
    recall_dispatch: RecordingDispatch,
    uow: UnitOfWork,
    publisher: RecordingPublisher,
    redis: Redis,
) -> Callable[[MockTelegram], DeliverBroadcastBatchUseCase]:
    def build(telegram: MockTelegram) -> DeliverBroadcastBatchUseCase:
        return DeliverBroadcastBatchUseCase(
            broadcast_repository,
            user_repository,
            settings_repository,
            promocode_repository,
            translation_repository,
            telegram,
            media_config,
            deliver_dispatch,
            recall_dispatch,
            uow,
            publisher,
            redis,
        )

    return build


@pytest.fixture
def tick_use_case(
    broadcast_repository: BroadcastRepository,
    start_dispatch: RecordingDispatch,
    deliver_dispatch: RecordingDispatch,
    email_dispatch: RecordingDispatch,
    uow: UnitOfWork,
) -> TickBroadcastsUseCase:
    return TickBroadcastsUseCase(
        broadcast_repository, start_dispatch, deliver_dispatch, email_dispatch, uow
    )


async def _customers(
    session: AsyncSession, user_repository: UserRepository, base_telegram_id: int, n: int
) -> list[int]:
    return [
        await make_customer(user_repository, session, telegram_id=base_telegram_id + i)
        for i in range(n)
    ]


async def _broadcast(
    repository: BroadcastRepository,
    status: BroadcastStatus,
    user_ids: list[int],
    **overrides: Any,
) -> BroadcastDto:
    created = await repository.create(
        save_dto(audience=BroadcastAudienceDto(user_ids=user_ids), **overrides), created_by=None
    )
    fields: dict[str, object] = {"status": status}
    if status is BroadcastStatus.SCHEDULED:
        fields["scheduled_at"] = datetime_now()
    await repository.update_fields(created.id, **fields)
    return await repository.get_by_id(created.id)


async def _sending(
    repository: BroadcastRepository, user_ids: list[int], **overrides: Any
) -> BroadcastDto:
    broadcast = await _broadcast(repository, BroadcastStatus.SENDING, user_ids, **overrides)
    total = await repository.materialize(
        broadcast.id,
        broadcast.audience,
        broadcast.category,
        broadcast.delivery,
        broadcast.email_fallback,
        datetime_now(),
    )
    await repository.update_fields(broadcast.id, total_count=total, started_at=datetime_now())
    return await repository.get_by_id(broadcast.id)


async def _recipients(session: AsyncSession, broadcast_id: int) -> list[BroadcastRecipient]:
    rows = await session.scalars(
        select(BroadcastRecipient)
        .where(BroadcastRecipient.broadcast_id == broadcast_id)
        .order_by(BroadcastRecipient.id)
        .execution_options(populate_existing=True)
    )
    return list(rows)


async def _statuses(session: AsyncSession, broadcast_id: int) -> list[BroadcastRecipientStatus]:
    return [r.status for r in await _recipients(session, broadcast_id)]


def _chat_id(request: httpx.Request) -> int:
    return int(json.loads(request.content)["chat_id"])


def _by_chat(responses: dict[int, httpx.Response]) -> Responder:
    return lambda request: responses[_chat_id(request)]


def _error(status: int, description: str = "err") -> httpx.Response:
    return httpx.Response(status, json={"ok": False, "description": description})


async def _photo(repository: BroadcastRepository, broadcast_id: int) -> None:
    await repository.update_fields(
        broadcast_id,
        media_type=BroadcastMediaType.PHOTO,
        media_extension="jpg",
        media_content_type="image/jpeg",
    )


async def test_start_materializes_and_kicks_deliver(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_start: Callable[[MockTelegram], StartBroadcastUseCase],
    deliver_dispatch: RecordingDispatch,
    publisher: RecordingPublisher,
) -> None:
    ids = await _customers(session, user_repository, 9600, 3)
    broadcast = await _broadcast(broadcast_repository, BroadcastStatus.SCHEDULED, ids)
    telegram = MockTelegram(ok_response)

    await make_start(telegram).system(broadcast.id)

    started = await broadcast_repository.get_by_id(broadcast.id)
    assert started.status is BroadcastStatus.SENDING
    assert started.total_count == 3
    assert started.started_at is not None
    assert deliver_dispatch.messages == [{"broadcast_id": broadcast.id}]
    assert _published(publisher) == [
        _strip(BroadcastStartedEvent(broadcast_id=broadcast.id, total=3, promocode_dropped=False))
    ]
    assert telegram.requests == []


async def test_start_waits_while_another_is_sending(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_start: Callable[[MockTelegram], StartBroadcastUseCase],
    deliver_dispatch: RecordingDispatch,
) -> None:
    ids = await _customers(session, user_repository, 9610, 1)
    await _sending(broadcast_repository, ids)
    waiting = await _broadcast(broadcast_repository, BroadcastStatus.SCHEDULED, ids)

    await make_start(MockTelegram(ok_response)).system(waiting.id)

    after = await broadcast_repository.get_by_id(waiting.id)
    assert after.status is BroadcastStatus.SCHEDULED
    assert after.started_at is None
    assert deliver_dispatch.messages == []


async def test_start_skips_materialize_on_retry(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_start: Callable[[MockTelegram], StartBroadcastUseCase],
) -> None:
    first, second, late = await _customers(session, user_repository, 9620, 3)
    broadcast = await _broadcast(
        broadcast_repository, BroadcastStatus.SCHEDULED, [first, second, late]
    )
    await broadcast_repository.materialize(
        broadcast.id,
        BroadcastAudienceDto(user_ids=[first, second]),
        broadcast.category,
        BroadcastDelivery.TELEGRAM,
        False,
        datetime_now(),
    )
    await broadcast_repository.update_fields(
        broadcast.id, total_count=2, started_at=datetime_now() - timedelta(hours=1)
    )

    await make_start(MockTelegram(ok_response)).system(broadcast.id)

    after = await broadcast_repository.get_by_id(broadcast.id)
    assert after.status is BroadcastStatus.SENDING
    assert after.total_count == 2
    assert len(await _recipients(session, broadcast.id)) == 2


async def test_start_drops_dead_promocode(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    promocode_repository: PromocodeRepository,
    make_start: Callable[[MockTelegram], StartBroadcastUseCase],
    publisher: RecordingPublisher,
) -> None:
    promo = await promocode_repository.create(
        CreatePromocodeDto(code="BCDEAD", reward_type=PromocodeRewardType.DURATION, reward=5)
    )
    ids = await _customers(session, user_repository, 9630, 1)
    broadcast = await _broadcast(
        broadcast_repository, BroadcastStatus.SCHEDULED, ids, promocode_id=promo.id
    )
    await session.execute(update(Promocode).where(Promocode.id == promo.id).values(is_active=False))

    await make_start(MockTelegram(ok_response)).system(broadcast.id)

    after = await broadcast_repository.get_by_id(broadcast.id)
    assert after.promocode_id is None
    assert after.status is BroadcastStatus.SENDING
    assert _published(publisher) == [
        _strip(BroadcastStartedEvent(broadcast_id=broadcast.id, total=1, promocode_dropped=True))
    ]


async def test_start_posts_to_channel(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    make_start: Callable[[MockTelegram], StartBroadcastUseCase],
    with_token: None,
) -> None:
    await settings_repository.update_bot_requirements(
        UpdateBotRequirementsDto(
            rules_required=False,
            rules_url=None,
            channel_required=False,
            channel_id=-100500,
            channel_url=None,
        )
    )
    ids = await _customers(session, user_repository, 9640, 1)
    broadcast = await _broadcast(
        broadcast_repository,
        BroadcastStatus.SCHEDULED,
        ids,
        post_to_channel=True,
        contents={save_dto().default_locale: BroadcastContentDto(text="News")},
    )
    telegram = MockTelegram(ok_response)

    await make_start(telegram).system(broadcast.id)

    assert len(telegram.requests) == 1
    assert telegram.requests[0].url.path == "/bot123:abc/sendMessage"
    assert _chat_id(telegram.requests[0]) == -100500
    after = await broadcast_repository.get_by_id(broadcast.id)
    assert (after.channel_chat_id, after.channel_message_id) == (-100500, 100)


async def test_deliver_marks_outcomes_and_completes(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    deliver_dispatch: RecordingDispatch,
    publisher: RecordingPublisher,
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9650, 3)
    broadcast = await _sending(broadcast_repository, ids)
    telegram = MockTelegram(
        _by_chat(
            {
                9650: httpx.Response(200, json={"ok": True, "result": {"message_id": 7}}),
                9651: _error(403, "Forbidden: bot was blocked by the user"),
                9652: _error(400, "Bad Request: chat not found"),
            }
        )
    )
    deliver = make_deliver(telegram)

    await deliver.system(broadcast.id)
    assert deliver_dispatch.messages == [{"broadcast_id": broadcast.id}]
    await deliver.system(broadcast.id)

    assert await _statuses(session, broadcast.id) == [
        BroadcastRecipientStatus.SENT,
        BroadcastRecipientStatus.BLOCKED,
        BroadcastRecipientStatus.FAILED,
    ]
    assert (await _recipients(session, broadcast.id))[0].telegram_message_id == 7
    after = await broadcast_repository.get_by_id(broadcast.id)
    assert after.status is BroadcastStatus.COMPLETED
    assert after.completed_at is not None
    assert (after.sent_count, after.blocked_count, after.failed_count) == (1, 1, 1)
    assert _published(publisher) == [
        _strip(BotBlockedByUserEvent(user_id=ids[1])),
        _strip(BroadcastCompletedEvent(broadcast_id=broadcast.id, sent=1, failed=1, blocked=1)),
    ]
    assert len(telegram.requests) == 3
    blocked = await user_repository.find_by_id(ids[1])
    assert blocked is not None and blocked.is_bot_blocked is True


async def test_deliver_skips_customers_who_blocked_the_bot(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9660, 2)
    broadcast = await _sending(broadcast_repository, ids)
    await user_repository.set_bot_blocked(ids[1], True)
    telegram = MockTelegram(
        _by_chat({9660: httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})})
    )

    await make_deliver(telegram).system(broadcast.id)

    assert await _statuses(session, broadcast.id) == [
        BroadcastRecipientStatus.SENT,
        BroadcastRecipientStatus.BLOCKED,
    ]
    assert len(telegram.requests) == 1


async def test_deliver_transient_error_retries_up_to_three(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    deliver_dispatch: RecordingDispatch,
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9660, 1)
    broadcast = await _sending(broadcast_repository, ids)
    deliver = make_deliver(MockTelegram(lambda request: _error(502, "Bad Gateway")))

    await deliver.system(broadcast.id)
    [recipient] = await _recipients(session, broadcast.id)
    assert (recipient.status, recipient.attempts) == (BroadcastRecipientStatus.PENDING, 1)
    assert deliver_dispatch.messages == [{"broadcast_id": broadcast.id}]

    await deliver.system(broadcast.id)
    await deliver.system(broadcast.id)
    [recipient] = await _recipients(session, broadcast.id)
    assert (recipient.status, recipient.attempts) == (BroadcastRecipientStatus.FAILED, 3)
    assert recipient.error == "Bad Gateway"


async def test_deliver_waits_on_429(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    with_token: None,
) -> None:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    ids = await _customers(session, user_repository, 9670, 1)
    broadcast = await _sending(broadcast_repository, ids)
    answers = iter(
        [
            httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 120}}),
            httpx.Response(200, json={"ok": True, "result": {"message_id": 1}}),
        ]
    )
    telegram = MockTelegram(lambda request: next(answers))

    await make_deliver(telegram).system(broadcast.id)

    assert await _statuses(session, broadcast.id) == [BroadcastRecipientStatus.SENT]
    assert len(telegram.requests) == 2
    assert sleeps[0] == deliver_module.MAX_RETRY_AFTER_S


async def test_deliver_stops_when_canceled(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    deliver_dispatch: RecordingDispatch,
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9680, 2)
    broadcast = await _sending(broadcast_repository, ids)
    await broadcast_repository.update_fields(broadcast.id, status=BroadcastStatus.CANCELED)
    telegram = MockTelegram(ok_response)

    await make_deliver(telegram).system(broadcast.id)

    assert telegram.requests == []
    assert deliver_dispatch.messages == []
    assert await _statuses(session, broadcast.id) == [BroadcastRecipientStatus.PENDING] * 2


async def test_deliver_uploads_media_once(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9690, 3)
    broadcast = await _sending(broadcast_repository, ids)
    await _photo(broadcast_repository, broadcast.id)
    _store_jpeg(media_config.media_dir, broadcast.id)

    def respond(request: httpx.Request) -> httpx.Response:
        if request.headers["content-type"].startswith("multipart/form-data"):
            photo = [{"file_id": "small"}, {"file_id": "F"}]
        else:
            assert json.loads(request.content)["photo"] == "F"
            photo = [{"file_id": "F"}]
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1, "photo": photo}})

    telegram = MockTelegram(respond)
    await make_deliver(telegram).system(broadcast.id)

    kinds = [r.headers["content-type"].split(";")[0] for r in telegram.requests]
    assert kinds == ["multipart/form-data", "application/json", "application/json"]
    assert all(r.url.path.endswith("/sendPhoto") for r in telegram.requests)
    assert await _statuses(session, broadcast.id) == [BroadcastRecipientStatus.SENT] * 3
    after = await broadcast_repository.get_by_id(broadcast.id)
    assert after.media_file_id == "F"


async def test_deliver_without_token_fails_broadcast(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    deliver_dispatch: RecordingDispatch,
    publisher: RecordingPublisher,
) -> None:
    ids = await _customers(session, user_repository, 9700, 2)
    broadcast = await _sending(broadcast_repository, ids)
    telegram = MockTelegram(ok_response)

    await make_deliver(telegram).system(broadcast.id)

    after = await broadcast_repository.get_by_id(broadcast.id)
    assert after.status is BroadcastStatus.FAILED
    assert after.completed_at is not None
    assert _published(publisher) == [
        _strip(BroadcastFailedEvent(broadcast_id=broadcast.id, error="Bot token is not set"))
    ]
    assert await _statuses(session, broadcast.id) == [BroadcastRecipientStatus.FAILED] * 2
    assert telegram.requests == []
    assert deliver_dispatch.messages == []


async def test_deliver_rejected_token_fails_broadcast(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    deliver_dispatch: RecordingDispatch,
    publisher: RecordingPublisher,
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9710, 3)
    broadcast = await _sending(broadcast_repository, ids)

    await make_deliver(MockTelegram(lambda request: _error(401, "Unauthorized"))).system(
        broadcast.id
    )

    after = await broadcast_repository.get_by_id(broadcast.id)
    assert after.status is BroadcastStatus.FAILED
    assert after.completed_at is not None
    assert _published(publisher) == [
        _strip(BroadcastFailedEvent(broadcast_id=broadcast.id, error="Bot token was rejected"))
    ]
    assert await _statuses(session, broadcast.id) == [BroadcastRecipientStatus.FAILED] * 3
    assert deliver_dispatch.messages == []


async def test_deliver_missing_media_file_fails_broadcast(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    publisher: RecordingPublisher,
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9720, 2)
    broadcast = await _sending(broadcast_repository, ids)
    await _photo(broadcast_repository, broadcast.id)
    telegram = MockTelegram(ok_response)

    await make_deliver(telegram).system(broadcast.id)

    after = await broadcast_repository.get_by_id(broadcast.id)
    assert after.status is BroadcastStatus.FAILED
    assert _published(publisher) == [
        _strip(BroadcastFailedEvent(broadcast_id=broadcast.id, error="Media file is missing"))
    ]
    assert telegram.requests == []
    assert await _statuses(session, broadcast.id) == [BroadcastRecipientStatus.FAILED] * 2


@pytest.mark.parametrize("with_media", [False, True])
async def test_recall_during_send_rekicks_after_in_flight_group(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    deliver_dispatch: RecordingDispatch,
    recall_dispatch: RecordingDispatch,
    publisher: RecordingPublisher,
    with_token: None,
    with_media: bool,
) -> None:
    ids = await _customers(session, user_repository, 9770 + 10 * with_media, 2)
    broadcast = await _sending(broadcast_repository, ids)
    if with_media:
        await _photo(broadcast_repository, broadcast.id)
        _store_jpeg(media_config.media_dir, broadcast.id)
    deliver = make_deliver(MockTelegram(ok_response))
    recall = RecallBroadcastUseCase(broadcast_repository, recall_dispatch, uow, publisher)
    record = deliver._record

    async def recall_while_in_flight(*args: Any) -> bool:
        if not recall_dispatch.messages:
            await recall.system(broadcast.id)
        return await record(*args)

    monkeypatch.setattr(deliver, "_record", recall_while_in_flight)

    await deliver.system(broadcast.id)

    # first kick from the recall itself, second from deliver once the group was recorded
    assert recall_dispatch.messages == [{"broadcast_id": broadcast.id}] * 2
    assert deliver_dispatch.messages == []
    statuses = await _statuses(session, broadcast.id)
    assert statuses[0] is BroadcastRecipientStatus.SENT
    expected_rest = (
        BroadcastRecipientStatus.CANCELED if with_media else BroadcastRecipientStatus.SENT
    )
    assert statuses[1] is expected_rest


async def test_recall_deletes_and_marks(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    recall_dispatch: RecordingDispatch,
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9730, 2)
    broadcast = await _sending(broadcast_repository, ids)
    for recipient, message_id in zip(await _recipients(session, broadcast.id), (11, 12)):
        await broadcast_repository.mark_recipient(
            recipient.id, BroadcastRecipientStatus.SENT, message_id=message_id
        )
    await broadcast_repository.update_fields(
        broadcast.id,
        status=BroadcastStatus.COMPLETED,
        channel_chat_id=-100500,
        channel_message_id=77,
    )
    # already deleted by hand: still counts as recalled
    telegram = MockTelegram(
        lambda request: (
            _error(400, "message to delete not found")
            if _chat_id(request) == 9731
            else httpx.Response(200, json={"ok": True, "result": True})
        )
    )

    await RecallBroadcastBatchUseCase(
        broadcast_repository, settings_repository, telegram, recall_dispatch, uow
    ).system(broadcast.id)

    deleted = sorted(
        (body["chat_id"], body["message_id"])
        for body in (json.loads(r.content) for r in telegram.requests)
    )
    assert deleted == [(-100500, 77), (9730, 11), (9731, 12)]
    assert all(r.url.path.endswith("/deleteMessage") for r in telegram.requests)
    assert await _statuses(session, broadcast.id) == [BroadcastRecipientStatus.RECALLED] * 2
    after = await broadcast_repository.get_by_id(broadcast.id)
    assert after.recalled_count == 2
    assert after.channel_message_id is None
    assert recall_dispatch.messages == []


async def _sent_broadcast(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    first_telegram_id: int,
    count: int,
) -> int:
    ids = await _customers(session, user_repository, first_telegram_id, count)
    broadcast = await _sending(broadcast_repository, ids)
    for message_id, recipient in enumerate(await _recipients(session, broadcast.id), start=1):
        await broadcast_repository.mark_recipient(
            recipient.id, BroadcastRecipientStatus.SENT, message_id=message_id
        )
    await broadcast_repository.update_fields(
        broadcast.id,
        status=BroadcastStatus.COMPLETED,
        channel_chat_id=-100500,
        channel_message_id=77,
    )
    return broadcast.id


async def test_recall_skips_unconfirmed_deletes_and_goes_on(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    recall_dispatch: RecordingDispatch,
    with_token: None,
) -> None:
    # a full page: the chain would otherwise re-kick for the next one
    monkeypatch.setattr(recall_module, "BATCH_SIZE", 3)
    broadcast_id = await _sent_broadcast(session, user_repository, broadcast_repository, 9740, 3)
    telegram = MockTelegram(
        _by_chat(
            {
                9740: httpx.Response(200, json={"ok": True, "result": True}),
                9741: _error(502),
                9742: _error(403, "blocked"),
            }
        )
    )

    await RecallBroadcastBatchUseCase(
        broadcast_repository, settings_repository, telegram, recall_dispatch, uow
    ).system(broadcast_id)

    assert await _statuses(session, broadcast_id) == [
        BroadcastRecipientStatus.RECALLED,
        BroadcastRecipientStatus.SENT,
        BroadcastRecipientStatus.RECALLED,
    ]
    # a transient failure doesn't drop the rest of the recall; the row is skipped, not looped over
    assert recall_dispatch.messages == [{"broadcast_id": broadcast_id}]
    assert await broadcast_repository.list_recallable(broadcast_id, 10) == []
    [kept] = [r for r in await _recipients(session, broadcast_id) if r.status == "SENT"]
    assert kept.error == "recall failed: err"


async def test_recall_stops_at_once_on_unauthorized(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    recall_dispatch: RecordingDispatch,
    with_token: None,
) -> None:
    monkeypatch.setattr(recall_module, "GROUP_SIZE", 1)
    broadcast_id = await _sent_broadcast(session, user_repository, broadcast_repository, 9750, 2)
    telegram = MockTelegram(lambda request: _error(401, "Unauthorized"))

    await RecallBroadcastBatchUseCase(
        broadcast_repository, settings_repository, telegram, recall_dispatch, uow
    ).system(broadcast_id)

    assert len(telegram.requests) == 1
    assert await _statuses(session, broadcast_id) == [BroadcastRecipientStatus.SENT] * 2
    assert (await broadcast_repository.get_by_id(broadcast_id)).channel_message_id == 77
    assert recall_dispatch.messages == []


async def test_recall_keeps_channel_post_it_could_not_delete(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    recall_dispatch: RecordingDispatch,
    with_token: None,
) -> None:
    broadcast_id = await _sent_broadcast(session, user_repository, broadcast_repository, 9760, 1)
    telegram = MockTelegram(
        _by_chat(
            {9760: httpx.Response(200, json={"ok": True, "result": True}), -100500: _error(502)}
        )
    )

    await RecallBroadcastBatchUseCase(
        broadcast_repository, settings_repository, telegram, recall_dispatch, uow
    ).system(broadcast_id)

    assert await _statuses(session, broadcast_id) == [BroadcastRecipientStatus.RECALLED]
    assert (await broadcast_repository.get_by_id(broadcast_id)).channel_message_id == 77


async def test_recall_rekicks_until_the_last_page(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    recall_dispatch: RecordingDispatch,
    with_token: None,
) -> None:
    monkeypatch.setattr(recall_module, "BATCH_SIZE", 1)
    broadcast_id = await _sent_broadcast(session, user_repository, broadcast_repository, 9770, 2)
    telegram = MockTelegram(ok_response)
    recall = RecallBroadcastBatchUseCase(
        broadcast_repository, settings_repository, telegram, recall_dispatch, uow
    )

    await recall.system(broadcast_id)
    assert recall_dispatch.messages == [{"broadcast_id": broadcast_id}]
    await recall.system(broadcast_id)
    await recall.system(broadcast_id)

    assert await _statuses(session, broadcast_id) == [BroadcastRecipientStatus.RECALLED] * 2
    assert len(recall_dispatch.messages) == 2


async def test_tick_starts_due_and_rekicks_stalled(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    tick_use_case: TickBroadcastsUseCase,
    start_dispatch: RecordingDispatch,
    deliver_dispatch: RecordingDispatch,
) -> None:
    ids = await _customers(session, user_repository, 9740, 1)
    stalled = await _sending(broadcast_repository, ids)
    await session.execute(
        update(Broadcast)
        .where(Broadcast.id == stalled.id)
        .values(updated_at=datetime_now() - timedelta(minutes=5))
    )
    due = await _broadcast(broadcast_repository, BroadcastStatus.SCHEDULED, ids)

    await tick_use_case.system()
    assert {"broadcast_id": stalled.id} in deliver_dispatch.messages
    # one at a time: the due one waits for the sending one
    assert start_dispatch.messages == []

    await broadcast_repository.update_fields(stalled.id, status=BroadcastStatus.COMPLETED)
    await tick_use_case.system()
    assert start_dispatch.messages == [{"broadcast_id": due.id}]


async def test_start_kicks_email_chain(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_start: Callable[[MockTelegram], StartBroadcastUseCase],
    deliver_dispatch: RecordingDispatch,
    email_dispatch: RecordingDispatch,
) -> None:
    ids = await _customers(session, user_repository, 9745, 1)
    broadcast = await _broadcast(
        broadcast_repository,
        BroadcastStatus.SCHEDULED,
        ids,
        delivery=BroadcastDelivery.ALL,
        email_contents={Locale.EN: BroadcastEmailContentDto(subject="Hi", html="<p>x</p>")},
    )

    await make_start(MockTelegram(ok_response)).system(broadcast.id)

    assert deliver_dispatch.messages == [{"broadcast_id": broadcast.id}]
    assert email_dispatch.messages == [{"broadcast_id": broadcast.id}]


async def test_tick_rekicks_both_chains_when_stalled(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    tick_use_case: TickBroadcastsUseCase,
    deliver_dispatch: RecordingDispatch,
    email_dispatch: RecordingDispatch,
) -> None:
    ids = await _customers(session, user_repository, 9747, 1)
    stalled = await _sending(broadcast_repository, ids)
    await session.execute(
        update(Broadcast)
        .where(Broadcast.id == stalled.id)
        .values(updated_at=datetime_now() - timedelta(minutes=5))
    )

    await tick_use_case.system()

    assert deliver_dispatch.messages == [{"broadcast_id": stalled.id}]
    assert email_dispatch.messages == [{"broadcast_id": stalled.id}]


async def test_two_send_now_run_one_after_another(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_start: Callable[[MockTelegram], StartBroadcastUseCase],
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    tick_use_case: TickBroadcastsUseCase,
    start_dispatch: RecordingDispatch,
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9750, 2)
    first = await _broadcast(broadcast_repository, BroadcastStatus.SCHEDULED, ids)
    second = await _broadcast(broadcast_repository, BroadcastStatus.SCHEDULED, ids)
    telegram = MockTelegram(ok_response)
    start = make_start(telegram)

    await start.system(first.id)
    await start.system(second.id)
    assert (await broadcast_repository.get_by_id(first.id)).status is BroadcastStatus.SENDING
    assert (await broadcast_repository.get_by_id(second.id)).status is BroadcastStatus.SCHEDULED

    deliver = make_deliver(telegram)
    await deliver.system(first.id)
    await deliver.system(first.id)
    assert (await broadcast_repository.get_by_id(first.id)).status is BroadcastStatus.COMPLETED

    await tick_use_case.system()
    assert start_dispatch.messages == [{"broadcast_id": second.id}]
    await start.system(second.id)
    assert (await broadcast_repository.get_by_id(second.id)).status is BroadcastStatus.SENDING


async def test_prune_keeps_counts(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    uow: UnitOfWork,
) -> None:
    ids = await _customers(session, user_repository, 9760, 2)
    broadcast = await _sending(broadcast_repository, ids)
    for recipient in await _recipients(session, broadcast.id):
        await broadcast_repository.mark_recipient(recipient.id, BroadcastRecipientStatus.SENT)
    await broadcast_repository.refresh_counts(broadcast.id)
    await broadcast_repository.update_fields(
        broadcast.id,
        status=BroadcastStatus.COMPLETED,
        completed_at=datetime_now() - timedelta(days=100),
    )

    pruned = await PruneBroadcastRecipientsUseCase(broadcast_repository, uow).system()

    assert pruned >= 2
    remaining = await session.scalar(
        select(func.count())
        .select_from(BroadcastRecipient)
        .where(BroadcastRecipient.broadcast_id == broadcast.id)
    )
    assert remaining == 0
    after = await broadcast_repository.get_by_id(broadcast.id)
    assert after.sent_count == 2
    assert after.total_count == 2


def _getme(username: object) -> Callable[[httpx.Request], httpx.Response]:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/getMe"):
            return httpx.Response(200, json={"ok": True, "result": {"username": username}})
        return ok_response(request)

    return respond


async def _channel_post_markup(
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    session: AsyncSession,
    user_repository: UserRepository,
    make_start: Callable[[MockTelegram], StartBroadcastUseCase],
    username: object,
) -> list[list[dict[str, str]]]:
    await settings_repository.update_bot_requirements(
        UpdateBotRequirementsDto(
            rules_required=False,
            rules_url=None,
            channel_required=False,
            channel_id=-100500,
            channel_url=None,
        )
    )
    ids = await _customers(session, user_repository, 9660, 1)
    broadcast = await _broadcast(
        broadcast_repository,
        BroadcastStatus.SCHEDULED,
        ids,
        post_to_channel=True,
        contents={
            save_dto().default_locale: BroadcastContentDto(
                text="News", button_labels=["Menu", "Go"]
            )
        },
        buttons=[
            BroadcastButtonDto(kind=BroadcastButtonKind.MENU),
            BroadcastButtonDto(kind=BroadcastButtonKind.URL, url="https://x.y"),
        ],
    )
    telegram = MockTelegram(_getme(username))
    await make_start(telegram).system(broadcast.id)
    sent = next(r for r in telegram.requests if r.url.path.endswith("/sendMessage"))
    markup = json.loads(sent.content).get("reply_markup") or {}
    return markup.get("inline_keyboard", [])


async def test_channel_post_links_menu_to_the_bot(
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    session: AsyncSession,
    user_repository: UserRepository,
    make_start: Callable[[MockTelegram], StartBroadcastUseCase],
    with_token: None,
) -> None:
    rows = await _channel_post_markup(
        broadcast_repository, settings_repository, session, user_repository, make_start, "shop_bot"
    )
    assert rows[0][0] == {"text": "Menu", "url": "https://t.me/shop_bot?start=menu"}


async def test_channel_post_without_username_drops_menu_button(
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    session: AsyncSession,
    user_repository: UserRepository,
    make_start: Callable[[MockTelegram], StartBroadcastUseCase],
    with_token: None,
) -> None:
    rows = await _channel_post_markup(
        broadcast_repository, settings_repository, session, user_repository, make_start, None
    )
    assert [row[0]["text"] for row in rows] == ["Go"]


async def test_get_bot_username_parses_get_me() -> None:
    async with MockTelegram(_getme("shop_bot")).open(None) as client:
        assert await get_bot_username(client, "t") == "shop_bot"
    async with MockTelegram(_getme(None)).open(None) as client:
        assert await get_bot_username(client, "t") is None


async def test_stop_by_cancel_counts_the_in_flight_group(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9790, 2)
    broadcast = await _sending(broadcast_repository, ids)
    deliver = make_deliver(MockTelegram(ok_response))
    record = deliver._record

    async def cancel_after_record(*args: Any) -> bool:
        result = await record(*args)
        await broadcast_repository.update_fields(broadcast.id, status=BroadcastStatus.CANCELED)
        return result

    monkeypatch.setattr(deliver, "_record", cancel_after_record)

    await deliver.system(broadcast.id)

    assert (await broadcast_repository.get_by_id(broadcast.id)).sent_count == 2


async def test_recall_waits_on_429_and_retries_once(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    recall_dispatch: RecordingDispatch,
    with_token: None,
) -> None:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    ids = await _customers(session, user_repository, 9830, 1)
    broadcast = await _sending(broadcast_repository, ids)
    [recipient] = await _recipients(session, broadcast.id)
    await broadcast_repository.mark_recipient(
        recipient.id, BroadcastRecipientStatus.SENT, message_id=5
    )
    answers = iter(
        [
            httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 120}}),
            httpx.Response(200, json={"ok": True, "result": True}),
        ]
    )
    telegram = MockTelegram(lambda request: next(answers))

    await RecallBroadcastBatchUseCase(
        broadcast_repository, settings_repository, telegram, recall_dispatch, uow
    ).system(broadcast.id)

    assert len(telegram.requests) == 2
    assert sleeps[0] == deliver_module.MAX_RETRY_AFTER_S
    assert await _statuses(session, broadcast.id) == [BroadcastRecipientStatus.RECALLED]


def _deliver_lock_key(broadcast_id: int) -> str:
    return f"{REDIS_KEY_PREFIX}broadcast_deliver:{broadcast_id}"


async def test_deliver_skips_while_another_chain_holds_the_lock(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    deliver_dispatch: RecordingDispatch,
    redis: Redis,
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9840, 2)
    broadcast = await _sending(broadcast_repository, ids)
    key = _deliver_lock_key(broadcast.id)
    await redis.set(key, "other", ex=300)
    try:
        telegram = MockTelegram(ok_response)

        await make_deliver(telegram).system(broadcast.id)

        assert telegram.requests == []
        assert deliver_dispatch.messages == []
        assert await _statuses(session, broadcast.id) == [BroadcastRecipientStatus.PENDING] * 2
        assert await redis.get(key) == "other"
    finally:
        await redis.delete(key)


@pytest.mark.parametrize("taken", [False, True])
async def test_deliver_reacquires_a_lapsed_lock_before_upload(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
    with_token: None,
    taken: bool,
) -> None:
    ids = await _customers(session, user_repository, 9870 + 10 * taken, 2)
    broadcast = await _sending(broadcast_repository, ids)
    await _photo(broadcast_repository, broadcast.id)
    _store_jpeg(media_config.media_dir, broadcast.id)
    key = _deliver_lock_key(broadcast.id)
    lapsed = [True]

    async def lapse(self: Lock) -> bool:
        if lapsed:
            lapsed.pop()
            await redis.set(key, "other", ex=300) if taken else await redis.delete(key)
            raise LockNotOwnedError("lapsed")
        return True

    monkeypatch.setattr(Lock, "reacquire", lapse)
    telegram = MockTelegram(ok_response)
    try:
        await make_deliver(telegram).system(broadcast.id)
    finally:
        await redis.delete(key)

    statuses = await _statuses(session, broadcast.id)
    if taken:
        assert telegram.requests == []
        assert statuses == [BroadcastRecipientStatus.PENDING] * 2
    else:
        assert statuses == [BroadcastRecipientStatus.SENT] * 2


async def test_deliver_releases_lock_before_chained_kick(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    deliver_dispatch: RecordingDispatch,
    redis: Redis,
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9850, 2)
    broadcast = await _sending(broadcast_repository, ids)
    held_at_kick: list[int] = []
    kiq = deliver_dispatch.kiq

    async def checking_kiq(**kwargs: Any) -> None:
        held_at_kick.append(await redis.exists(_deliver_lock_key(broadcast.id)))
        await kiq(**kwargs)

    deliver_dispatch.kiq = checking_kiq  # type: ignore[method-assign]
    deliver = make_deliver(MockTelegram(ok_response))

    await deliver.system(broadcast.id)
    assert held_at_kick == [0]
    await deliver.system(broadcast.id)

    assert (await broadcast_repository.get_by_id(broadcast.id)).status is (
        BroadcastStatus.COMPLETED
    )
    assert not await redis.exists(_deliver_lock_key(broadcast.id))


async def test_deliver_records_each_send_and_releases_lock_on_error(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    redis: Redis,
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9860, 3)
    broadcast = await _sending(broadcast_repository, ids)

    def respond(request: httpx.Request) -> httpx.Response:
        if _chat_id(request) == 9862:
            raise RuntimeError("boom")
        return ok_response(request)

    with pytest.raises(RuntimeError):
        await make_deliver(MockTelegram(respond)).system(broadcast.id)

    assert await _statuses(session, broadcast.id) == [
        BroadcastRecipientStatus.SENT,
        BroadcastRecipientStatus.SENT,
        BroadcastRecipientStatus.PENDING,
    ]
    assert not await redis.exists(_deliver_lock_key(broadcast.id))


async def test_deliver_does_not_skip_a_row_locked_elsewhere(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9870, 1)
    broadcast = await _sending(broadcast_repository, ids)

    async def skipped(broadcast_id: int) -> None:
        return None

    # what SKIP LOCKED answers while a short admin transaction holds the row
    monkeypatch.setattr(broadcast_repository, "try_lock", skipped)

    await make_deliver(MockTelegram(ok_response)).system(broadcast.id)

    assert await _statuses(session, broadcast.id) == [BroadcastRecipientStatus.SENT]


async def test_deliver_flood_waits_do_not_count_attempts(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    with_token: None,
) -> None:
    async def fake_sleep(delay: float) -> None:
        pass

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    ids = await _customers(session, user_repository, 9880, 1)
    broadcast = await _sending(broadcast_repository, ids)
    flood = httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 3}})
    answers = iter([flood, flood, flood, ok_response(httpx.Request("POST", "http://x"))])
    telegram = MockTelegram(lambda request: next(answers))

    await make_deliver(telegram).system(broadcast.id)

    [recipient] = await _recipients(session, broadcast.id)
    assert (recipient.status, recipient.attempts) == (BroadcastRecipientStatus.SENT, 0)
    assert len(telegram.requests) == 4


async def test_deliver_flood_wait_over_cap_counts_an_attempt(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    with_token: None,
) -> None:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    ids = await _customers(session, user_repository, 9890, 1)
    broadcast = await _sending(broadcast_repository, ids)
    telegram = MockTelegram(
        lambda request: httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 120}})
    )

    await make_deliver(telegram).system(broadcast.id)

    [recipient] = await _recipients(session, broadcast.id)
    assert (recipient.status, recipient.attempts) == (BroadcastRecipientStatus.PENDING, 1)
    flood_waits = [s for s in sleeps if s]
    assert sum(flood_waits) <= deliver_module.MAX_FLOOD_WAIT_S
    assert len(telegram.requests) == 1 + len(flood_waits)


async def test_deliver_survives_deletion_mid_group(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    deliver_dispatch: RecordingDispatch,
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9900, 2)
    broadcast = await _sending(broadcast_repository, ids)
    deliver = make_deliver(MockTelegram(ok_response))
    record = deliver._record

    async def delete_after_record(*args: Any) -> bool:
        result = await record(*args)
        await session.execute(delete(Broadcast).where(Broadcast.id == broadcast.id))
        return result

    monkeypatch.setattr(deliver, "_record", delete_after_record)

    await deliver.system(broadcast.id)

    assert deliver_dispatch.messages == []
    assert await broadcast_repository.find_by_id(broadcast.id) is None


async def test_retry_after_rejected_token_resends_unsent(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    start_dispatch: RecordingDispatch,
    uow: UnitOfWork,
    publisher: RecordingPublisher,
    with_token: None,
) -> None:
    ids = await _customers(session, user_repository, 9910, 3)
    broadcast = await _sending(broadcast_repository, ids)
    await make_deliver(MockTelegram(lambda request: _error(401, "Unauthorized"))).system(
        broadcast.id
    )
    assert (await broadcast_repository.get_by_id(broadcast.id)).status is (BroadcastStatus.FAILED)

    result = await RetryBroadcastUseCase(
        broadcast_repository, start_dispatch, uow, publisher
    ).system(broadcast.id)

    assert result.status is BroadcastStatus.SCHEDULED
    assert result.failed_count == 0
    assert await _statuses(session, broadcast.id) == [BroadcastRecipientStatus.PENDING] * 3
    assert start_dispatch.messages == [{"broadcast_id": broadcast.id}]


async def test_recall_can_be_requested_again_while_messages_remain(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    uow: UnitOfWork,
    recall_dispatch: RecordingDispatch,
    publisher: RecordingPublisher,
) -> None:
    broadcast_id = await _sent_broadcast(session, user_repository, broadcast_repository, 9780, 2)
    first, second = await _recipients(session, broadcast_id)
    await broadcast_repository.mark_recipient(first.id, BroadcastRecipientStatus.RECALLED)
    await broadcast_repository.mark_recall_failed(second.id, "err")
    await broadcast_repository.update_fields(
        broadcast_id,
        recall_requested_at=datetime_now() - timedelta(minutes=10),
        channel_message_id=None,
    )
    await broadcast_repository.refresh_counts(broadcast_id)
    recall = RecallBroadcastUseCase(broadcast_repository, recall_dispatch, uow, publisher)

    await recall.system(broadcast_id)

    assert recall_dispatch.messages == [{"broadcast_id": broadcast_id}]
    assert [r.id for r in await broadcast_repository.list_recallable(broadcast_id, 10)] == [
        second.id
    ]

    await broadcast_repository.mark_recipient(second.id, BroadcastRecipientStatus.RECALLED)
    await broadcast_repository.update_fields(
        broadcast_id, recall_requested_at=datetime_now() - timedelta(minutes=10)
    )
    await broadcast_repository.refresh_counts(broadcast_id)
    with pytest.raises(ConflictError):
        await recall.system(broadcast_id)


async def test_recall_repeat_is_refused_while_the_last_one_runs(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    uow: UnitOfWork,
    recall_dispatch: RecordingDispatch,
    publisher: RecordingPublisher,
) -> None:
    broadcast_id = await _sent_broadcast(session, user_repository, broadcast_repository, 9790, 1)
    await broadcast_repository.update_fields(broadcast_id, recall_requested_at=datetime_now())
    recall = RecallBroadcastUseCase(broadcast_repository, recall_dispatch, uow, publisher)

    with pytest.raises(ConflictError) as error:
        await recall.system(broadcast_id)

    assert error.value.code is ErrorCode.BROADCAST_RECALL_IN_PROGRESS
    assert recall_dispatch.messages == []


async def test_recall_repeat_is_refused_when_no_row_can_be_recalled(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    uow: UnitOfWork,
    recall_dispatch: RecordingDispatch,
    publisher: RecordingPublisher,
) -> None:
    broadcast_id = await _sent_broadcast(session, user_repository, broadcast_repository, 9795, 1)
    [recipient] = await _recipients(session, broadcast_id)
    # the customer lost their Telegram account (e.g. merged away)
    await session.execute(update(User).where(User.id == recipient.user_id).values(telegram_id=None))
    await broadcast_repository.update_fields(
        broadcast_id,
        recall_requested_at=datetime_now() - timedelta(minutes=10),
        channel_message_id=None,
    )
    await broadcast_repository.refresh_counts(broadcast_id)
    recall = RecallBroadcastUseCase(broadcast_repository, recall_dispatch, uow, publisher)

    with pytest.raises(ConflictError) as error:
        await recall.system(broadcast_id)

    assert error.value.code is ErrorCode.BROADCAST_INVALID_STATUS


async def test_get_broadcast_reports_how_many_rows_can_be_recalled(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    uow: UnitOfWork,
) -> None:
    broadcast_id = await _sent_broadcast(session, user_repository, broadcast_repository, 9798, 2)
    first, _ = await _recipients(session, broadcast_id)
    await broadcast_repository.mark_recipient(first.id, BroadcastRecipientStatus.RECALLED)

    broadcast = await GetBroadcastUseCase(broadcast_repository, uow).system(broadcast_id)

    assert broadcast.recallable_count == 1


async def test_a_running_recall_chain_keeps_its_repeat_window_fresh(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    recall_dispatch: RecordingDispatch,
    with_token: None,
) -> None:
    monkeypatch.setattr(recall_module, "BATCH_SIZE", 1)
    broadcast_id = await _sent_broadcast(session, user_repository, broadcast_repository, 9800, 2)
    requested = datetime_now() - timedelta(minutes=10)
    await broadcast_repository.update_fields(broadcast_id, recall_requested_at=requested)
    recall = RecallBroadcastBatchUseCase(
        broadcast_repository, settings_repository, MockTelegram(ok_response), recall_dispatch, uow
    )

    # a full page means more is coming, so the chain is still running
    await recall.system(broadcast_id)

    refreshed = await broadcast_repository.get_by_id(broadcast_id)
    assert refreshed.recall_requested_at is not None
    assert refreshed.recall_requested_at > requested + timedelta(minutes=5)


async def test_email_only_broadcast_needs_no_bot(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    publisher: RecordingPublisher,
) -> None:
    user = await make_customer(user_repository, session, telegram_id=None, email="m@x.example")
    broadcast = await _sending(
        broadcast_repository,
        [user],
        delivery=BroadcastDelivery.EMAIL,
        contents={},
        email_contents={Locale.EN: BroadcastEmailContentDto(subject="s", html="<p>b</p>")},
    )
    telegram = MockTelegram(ok_response)

    await make_deliver(telegram).system(broadcast.id)

    after = await broadcast_repository.get_by_id(broadcast.id)
    # the email row waits for its own chain, not failed for a missing bot
    assert after.status is BroadcastStatus.SENDING
    assert await _statuses(session, broadcast.id) == [BroadcastRecipientStatus.PENDING]
    assert publisher.events == []
    assert telegram.requests == []


async def test_complete_once_when_both_chains_finish(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[[MockTelegram], DeliverBroadcastBatchUseCase],
    publisher: RecordingPublisher,
    with_token: None,
) -> None:
    user = await make_customer(user_repository, session, telegram_id=9990, email="b@x.example")
    broadcast = await _sending(broadcast_repository, [user], delivery=BroadcastDelivery.ALL)
    assert broadcast.total_count == 2
    await session.execute(
        update(BroadcastRecipient)
        .where(
            BroadcastRecipient.broadcast_id == broadcast.id,
            BroadcastRecipient.channel == BroadcastChannel.EMAIL,
        )
        .values(status=BroadcastRecipientStatus.SENT)
    )
    telegram = MockTelegram(ok_response)
    deliver = make_deliver(telegram)

    await deliver.system(broadcast.id)
    await deliver.system(broadcast.id)
    await deliver.system(broadcast.id)

    after = await broadcast_repository.get_by_id(broadcast.id)
    assert after.status is BroadcastStatus.COMPLETED
    assert after.sent_count == 2
    assert _published(publisher) == [
        _strip(BroadcastCompletedEvent(broadcast_id=broadcast.id, sent=2, failed=0, blocked=0))
    ]
    assert len(telegram.requests) == 1
