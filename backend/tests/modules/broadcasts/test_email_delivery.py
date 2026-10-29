import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

import pytest
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.config.cabinet import CabinetConfig
from app.core.constants import REDIS_KEY_PREFIX
from app.core.db.models.broadcast import Broadcast
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    AppearanceImageKind,
    AppearanceTarget,
    BroadcastCategory,
    BroadcastDelivery,
    BroadcastRecipientStatus,
    BroadcastStatus,
    EmailOutcome,
    Locale,
)
from app.core.metrics import WORKER_METRICS_REGISTRY
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dto import BroadcastDto, BroadcastEmailContentDto
from app.modules.broadcasts.events import BroadcastCompletedEvent
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.storage import email_image_path
from app.modules.broadcasts.usecases import DeliverBroadcastEmailBatchUseCase
from app.modules.broadcasts.usecases import deliver_broadcast_email_batch as email_module
from app.modules.email import (
    EmailDeliveryDto,
    EmailSendError,
    InlineImageDto,
    OutgoingEmailDto,
    smtp_pause_key,
)
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.settings import GetPublicAppearanceImageUseCase
from app.modules.settings.appearance_storage import appearance_image_path
from app.modules.settings.dto import SmtpProfileDto, UpdateEmailSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.translations.repository import TranslationRepository
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.broadcasts.factories import make_customer
from tests.modules.broadcasts.test_worker_usecases import (
    RecordingPublisher,
    _recipients,
    _sending,
)


class FakeBatch:
    def __init__(
        self,
        outcomes: dict[str, EmailDeliveryDto],
        sent: list[OutgoingEmailDto],
        drop_after: Optional[int] = None,
    ) -> None:
        self._outcomes, self.sent, self._drop_after = outcomes, sent, drop_after

    async def send(self, email: OutgoingEmailDto) -> EmailDeliveryDto:
        if self._drop_after is not None and len(self.sent) >= self._drop_after:
            raise EmailSendError("connection lost", connection=True)
        self.sent.append(email)
        return self._outcomes.get(email.to, EmailDeliveryDto(outcome=EmailOutcome.SENT))


class FakeBatchSender:
    def __init__(
        self,
        outcomes: Optional[dict[str, EmailDeliveryDto]] = None,
        connect_error: bool = False,
        auth_error: bool = False,
        drop_after: Optional[int] = None,
    ) -> None:
        self.outcomes, self.connect_error = outcomes or {}, connect_error
        self.auth_error, self.drop_after = auth_error, drop_after
        self.sent: list[OutgoingEmailDto] = []
        self.profiles: list[SmtpProfileDto] = []

    @asynccontextmanager
    async def open(self, profile: SmtpProfileDto) -> AsyncIterator[FakeBatch]:
        self.profiles.append(profile)
        if self.connect_error:
            raise EmailSendError("down", connection=True)
        if self.auth_error:
            raise EmailSendError("535 bad credentials", auth=True)
        yield FakeBatch(self.outcomes, self.sent, self.drop_after)


def _metric(result: str) -> float:
    return (
        WORKER_METRICS_REGISTRY.get_sample_value(
            "remnashop_broadcast_emails_total", {"result": result}
        )
        or 0.0
    )


@pytest.fixture(autouse=True)
def _no_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_module, "EMAIL_BATCH_WINDOW_S", 0)


@pytest.fixture
def media_config(config: AppConfig, tmp_path: Path) -> AppConfig:
    return config.model_copy(update={"media_dir": tmp_path})


@pytest.fixture
def email_dispatch() -> RecordingDispatch:
    return RecordingDispatch()


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
async def smtp(settings_repository: SettingsRepository) -> None:
    await settings_repository.update_email_settings(
        UpdateEmailSettingsDto(host="smtp.example.com", from_address="shop@example.com")
    )


@pytest.fixture
def make_deliver(
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    promocode_repository: PromocodeRepository,
    translation_repository: TranslationRepository,
    user_repository: UserRepository,
    media_config: AppConfig,
    email_dispatch: RecordingDispatch,
    uow: UnitOfWork,
    publisher: RecordingPublisher,
    redis: Redis,
) -> Callable[..., DeliverBroadcastEmailBatchUseCase]:
    def build(
        sender: FakeBatchSender, config: Optional[AppConfig] = None
    ) -> DeliverBroadcastEmailBatchUseCase:
        cfg = config or media_config
        return DeliverBroadcastEmailBatchUseCase(
            broadcast_repository,
            settings_repository,
            promocode_repository,
            translation_repository,
            user_repository,
            GetPublicAppearanceImageUseCase(settings_repository, cfg, uow),
            sender,  # type: ignore[arg-type]
            cfg,
            email_dispatch,
            uow,
            publisher,
            redis,
        )

    return build


async def _users(
    session: AsyncSession, user_repository: UserRepository, base: int, n: int
) -> list[int]:
    return [
        await make_customer(
            user_repository, session, telegram_id=None, email=f"u{base + i}@example.com"
        )
        for i in range(n)
    ]


async def _email_broadcast(
    repository: BroadcastRepository,
    user_ids: list[int],
    html: str = "<p>Hi { $name }</p>",
    **kw: Any,
) -> BroadcastDto:
    return await _sending(
        repository,
        user_ids,
        delivery=BroadcastDelivery.EMAIL,
        email_contents={Locale.EN: BroadcastEmailContentDto(subject="News", html=html)},
        **kw,
    )


async def test_sends_and_completes(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    email_dispatch: RecordingDispatch,
    publisher: RecordingPublisher,
    smtp: None,
) -> None:
    ids = await _users(session, user_repository, 100, 2)
    broadcast = await _email_broadcast(broadcast_repository, ids)
    sender = FakeBatchSender()
    before = _metric("sent")

    deliver = make_deliver(sender)
    await deliver.system(broadcast.id)
    assert email_dispatch.messages == [{"broadcast_id": broadcast.id}]
    await deliver.system(broadcast.id)

    assert [r.status for r in await _recipients(session, broadcast.id)] == [
        BroadcastRecipientStatus.SENT,
        BroadcastRecipientStatus.SENT,
    ]
    assert sorted(e.to for e in sender.sent) == ["u100@example.com", "u101@example.com"]
    after = await broadcast_repository.get_by_id(broadcast.id)
    assert after.status is BroadcastStatus.COMPLETED
    completed = [e for e in publisher.events if isinstance(e, BroadcastCompletedEvent)]
    assert len(completed) == 1
    assert completed[0].sent == 2
    assert _metric("sent") - before == 2
    # second run completes without a re-kick
    assert email_dispatch.messages == [{"broadcast_id": broadcast.id}]


async def test_permanent_refusal_marks_user_undeliverable(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    smtp: None,
) -> None:
    bad, good = await _users(session, user_repository, 110, 2)
    broadcast = await _email_broadcast(broadcast_repository, [bad, good])
    sender = FakeBatchSender(
        {"u110@example.com": EmailDeliveryDto(outcome=EmailOutcome.REFUSED, error="550")}
    )
    before = _metric("undeliverable")

    await make_deliver(sender).system(broadcast.id)

    rows = {r.user_id: r for r in await _recipients(session, broadcast.id)}
    assert rows[bad].status is BroadcastRecipientStatus.FAILED
    assert rows[bad].error == "undeliverable"
    assert rows[good].status is BroadcastRecipientStatus.SENT
    user = await session.scalar(
        select(User).where(User.id == bad).execution_options(populate_existing=True)
    )
    assert user is not None and user.email_undeliverable_at is not None
    assert _metric("undeliverable") - before == 1


async def test_retry_until_max_attempts(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    smtp: None,
) -> None:
    ids = await _users(session, user_repository, 120, 1)
    broadcast = await _email_broadcast(broadcast_repository, ids)
    sender = FakeBatchSender(
        {"u120@example.com": EmailDeliveryDto(outcome=EmailOutcome.RETRY, error="451 later")}
    )
    deliver = make_deliver(sender)
    before = _metric("failed")

    await deliver.system(broadcast.id)
    [row] = await _recipients(session, broadcast.id)
    assert (row.status, row.attempts) == (BroadcastRecipientStatus.PENDING, 1)
    await deliver.system(broadcast.id)
    assert _metric("failed") == before
    await deliver.system(broadcast.id)

    [row] = await _recipients(session, broadcast.id)
    assert (row.status, row.attempts) == (BroadcastRecipientStatus.FAILED, 3)
    assert row.error == "451 later"
    assert _metric("failed") - before == 1


async def test_connection_error_pauses_without_spending_attempts(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    email_dispatch: RecordingDispatch,
    redis: Redis,
    smtp: None,
) -> None:
    ids = await _users(session, user_repository, 130, 2)
    broadcast = await _email_broadcast(broadcast_repository, ids)
    down = FakeBatchSender(connect_error=True)

    await make_deliver(down).system(broadcast.id)

    for row in await _recipients(session, broadcast.id):
        assert row.status is BroadcastRecipientStatus.PENDING
        assert row.attempts == 0
        assert row.claimed_until is None
    ttl = await redis.ttl(smtp_pause_key(bulk=False))
    assert 0 < ttl <= 60
    assert email_dispatch.messages == [{"broadcast_id": broadcast.id}]

    healthy = FakeBatchSender()
    await make_deliver(healthy).system(broadcast.id)
    assert healthy.sent == []
    assert healthy.profiles == []
    assert email_dispatch.messages == [{"broadcast_id": broadcast.id}] * 2


async def test_connection_lost_mid_batch_keeps_the_letters_already_sent(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    smtp: None,
) -> None:
    ids = await _users(session, user_repository, 140, 3)
    broadcast = await _email_broadcast(broadcast_repository, ids)

    await make_deliver(FakeBatchSender(drop_after=1)).system(broadcast.id)

    statuses = [r.status for r in await _recipients(session, broadcast.id)]
    assert statuses == [
        BroadcastRecipientStatus.SENT,
        BroadcastRecipientStatus.PENDING,
        BroadcastRecipientStatus.PENDING,
    ]


async def test_auth_error_fails_broadcast(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    email_dispatch: RecordingDispatch,
    redis: Redis,
    smtp: None,
) -> None:
    ids = await _users(session, user_repository, 135, 2)
    broadcast = await _email_broadcast(broadcast_repository, ids)

    await make_deliver(FakeBatchSender(auth_error=True)).system(broadcast.id)

    after = await broadcast_repository.get_by_id(broadcast.id)
    assert after.status is BroadcastStatus.FAILED
    for row in await _recipients(session, broadcast.id):
        assert row.status is BroadcastRecipientStatus.FAILED
        assert row.claimed_until is None
    assert not await redis.exists(smtp_pause_key(bulk=False))
    assert email_dispatch.messages == []


async def test_uses_bulk_profile_and_rate(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    smtp: None,
) -> None:
    await settings_repository.update_email_settings(
        UpdateEmailSettingsDto(
            bulk_host="bulk.example.com",
            bulk_from_address="news@example.com",
            bulk_rate_per_minute=1,
        )
    )
    ids = await _users(session, user_repository, 140, 2)
    broadcast = await _email_broadcast(broadcast_repository, ids)
    sender = FakeBatchSender()

    await make_deliver(sender).system(broadcast.id)

    assert len(sender.sent) == 1
    [profile] = sender.profiles
    assert profile.is_bulk
    assert profile.host == "bulk.example.com"


async def test_marketing_email_has_unsubscribe_header(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    media_config: AppConfig,
    smtp: None,
) -> None:
    ids = await _users(session, user_repository, 150, 1)
    broadcast = await _email_broadcast(
        broadcast_repository, ids, category=BroadcastCategory.MARKETING
    )
    sender = FakeBatchSender()
    config = media_config.model_copy(update={"cabinet": CabinetConfig(domain="cab.example")})

    await make_deliver(sender, config).system(broadcast.id)

    [email] = sender.sent
    assert email.headers["List-Unsubscribe"].startswith("<https://cab.example/api/unsubscribe?")
    assert email.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


async def test_canceled_stops_chain(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    email_dispatch: RecordingDispatch,
    smtp: None,
) -> None:
    ids = await _users(session, user_repository, 160, 1)
    broadcast = await _email_broadcast(broadcast_repository, ids)
    await broadcast_repository.update_fields(broadcast.id, status=BroadcastStatus.CANCELED)
    sender = FakeBatchSender()

    await make_deliver(sender).system(broadcast.id)

    assert sender.sent == []
    assert email_dispatch.messages == []


@pytest.mark.parametrize("with_logo", [False, True])
async def test_inline_images_attached(
    with_logo: bool,
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    media_config: AppConfig,
    smtp: None,
) -> None:
    if with_logo:
        await settings_repository.set_appearance_image(
            AppearanceTarget.DASHBOARD, AppearanceImageKind.LOGO, "image/png", "png"
        )
        logo_path = appearance_image_path(
            media_config.media_dir, AppearanceTarget.DASHBOARD, AppearanceImageKind.LOGO, "png"
        )
        logo_path.parent.mkdir(parents=True, exist_ok=True)
        logo_path.write_bytes(b"logo")
    ids = await _users(session, user_repository, 170, 1)
    broadcast = await _email_broadcast(broadcast_repository, ids)
    image = await broadcast_repository.add_email_image(broadcast.id, "image/png", "png", 3)
    path = email_image_path(media_config.media_dir, broadcast.id, image.id, "png")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"png")
    await broadcast_repository.update_fields(
        broadcast.id,
        email_contents={
            Locale.EN.value: {"subject": "News", "html": f'<p><img src="bc-image:{image.id}"></p>'}
        },
    )
    sender = FakeBatchSender()

    await make_deliver(sender).system(broadcast.id)

    [email] = sender.sent
    expected = [InlineImageDto(cid=f"img-{image.id}", data=b"png", content_type="image/png")]
    if with_logo:
        expected.append(InlineImageDto(cid="logo", data=b"logo", content_type="image/png"))
    assert email.images == expected
    assert f"cid:img-{image.id}" in email.html
    assert ("cid:logo" in email.html) is with_logo


async def test_opted_out_between_materialize_and_send(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    smtp: None,
) -> None:
    ids = await _users(session, user_repository, 180, 1)
    broadcast = await _email_broadcast(
        broadcast_repository, ids, category=BroadcastCategory.MARKETING
    )
    await session.execute(update(User).where(User.id == ids[0]).values(marketing_opt_out=True))
    sender = FakeBatchSender()

    await make_deliver(sender).system(broadcast.id)

    [row] = await _recipients(session, broadcast.id)
    assert row.status is BroadcastRecipientStatus.CANCELED
    assert sender.sent == []


async def test_email_chain_ignores_telegram_only_broadcast(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    email_dispatch: RecordingDispatch,
) -> None:
    uid = await make_customer(user_repository, session, telegram_id=9900)
    broadcast = await _sending(broadcast_repository, [uid])

    await make_deliver(FakeBatchSender()).system(broadcast.id)

    after = await broadcast_repository.get_by_id(broadcast.id)
    assert after.status is BroadcastStatus.SENDING
    [row] = await _recipients(session, broadcast.id)
    assert row.status is BroadcastRecipientStatus.PENDING
    assert email_dispatch.messages == []


async def _age(session: AsyncSession, broadcast_id: int) -> None:
    await session.execute(
        update(Broadcast)
        .where(Broadcast.id == broadcast_id)
        .values(updated_at=datetime_now() - timedelta(minutes=10))
    )


async def _updated_at(session: AsyncSession, broadcast_id: int) -> Any:
    return await session.scalar(
        select(Broadcast.updated_at)
        .where(Broadcast.id == broadcast_id)
        .execution_options(populate_existing=True)
    )


async def test_pause_keeps_heartbeat(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    redis: Redis,
    smtp: None,
) -> None:
    ids = await _users(session, user_repository, 200, 1)
    broadcast = await _email_broadcast(broadcast_repository, ids)
    await redis.set(smtp_pause_key(bulk=False), "1", ex=60)
    await _age(session, broadcast.id)

    await make_deliver(FakeBatchSender()).system(broadcast.id)

    assert await _updated_at(session, broadcast.id) > datetime_now() - timedelta(minutes=1)


async def test_connection_error_keeps_heartbeat(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    smtp: None,
) -> None:
    ids = await _users(session, user_repository, 205, 1)
    broadcast = await _email_broadcast(broadcast_repository, ids)
    await _age(session, broadcast.id)

    await make_deliver(FakeBatchSender(connect_error=True)).system(broadcast.id)

    assert await _updated_at(session, broadcast.id) > datetime_now() - timedelta(minutes=1)


async def test_run_while_lock_held_sends_nothing(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    email_dispatch: RecordingDispatch,
    redis: Redis,
    smtp: None,
) -> None:
    ids = await _users(session, user_repository, 210, 1)
    broadcast = await _email_broadcast(broadcast_repository, ids)
    other = redis.lock(f"{REDIS_KEY_PREFIX}broadcast_deliver_email:{broadcast.id}", timeout=60)
    assert await other.acquire(blocking=False)
    sender = FakeBatchSender()

    await make_deliver(sender).system(broadcast.id)

    assert sender.sent == []
    assert email_dispatch.messages == []


async def test_lock_held_through_pacing_sleep(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    settings_repository: SettingsRepository,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    email_dispatch: RecordingDispatch,
    smtp: None,
) -> None:
    await settings_repository.update_email_settings(UpdateEmailSettingsDto(bulk_rate_per_minute=1))
    ids = await _users(session, user_repository, 220, 2)
    broadcast = await _email_broadcast(broadcast_repository, ids)
    intruder = FakeBatchSender()
    real_sleep = asyncio.sleep

    async def sleep_and_intrude(delay: float) -> None:
        await make_deliver(intruder).system(broadcast.id)
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", sleep_and_intrude)

    await make_deliver(FakeBatchSender()).system(broadcast.id)

    assert intruder.sent == []
    assert email_dispatch.messages == [{"broadcast_id": broadcast.id}]


async def test_no_rekick_when_canceled_during_sleep(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    email_dispatch: RecordingDispatch,
    smtp: None,
) -> None:
    ids = await _users(session, user_repository, 230, 2)
    broadcast = await _email_broadcast(broadcast_repository, ids)
    real_sleep = asyncio.sleep

    async def sleep_and_cancel(delay: float) -> None:
        await broadcast_repository.update_fields(broadcast.id, status=BroadcastStatus.CANCELED)
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", sleep_and_cancel)

    await make_deliver(FakeBatchSender()).system(broadcast.id)

    assert email_dispatch.messages == []


async def test_unreferenced_missing_image_is_ignored(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    smtp: None,
) -> None:
    ids = await _users(session, user_repository, 240, 1)
    broadcast = await _email_broadcast(broadcast_repository, ids)
    await broadcast_repository.add_email_image(broadcast.id, "image/png", "png", 3)
    sender = FakeBatchSender()

    await make_deliver(sender).system(broadcast.id)

    [email] = sender.sent
    assert email.images == []


async def test_referenced_image_without_row_fails_broadcast(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    make_deliver: Callable[..., DeliverBroadcastEmailBatchUseCase],
    smtp: None,
) -> None:
    ids = await _users(session, user_repository, 250, 1)
    broadcast = await _email_broadcast(
        broadcast_repository, ids, html='<p><img src="bc-image:999999"></p>'
    )
    sender = FakeBatchSender()

    await make_deliver(sender).system(broadcast.id)

    assert sender.sent == []
    after = await broadcast_repository.get_by_id(broadcast.id)
    assert after.status is BroadcastStatus.FAILED
