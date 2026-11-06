from datetime import timedelta

import httpx
import pytest
from pydantic import ValidationError
from redis.asyncio import Redis
from remnapy import RemnawaveSDK
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.backup_run import BackupRun
from app.core.db.models.broadcast import Broadcast
from app.core.db.models.event_outbox import EventOutboxEntry
from app.core.db.models.transaction import Transaction
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    BackupKind,
    BroadcastStatus,
    Locale,
    Role,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.events import EventCategory
from app.core.exceptions import RemnawavePanelUnavailableError
from app.core.runtime_heartbeat import publish_runtime_heartbeat
from app.core.utils.time import datetime_now
from app.modules.api_tokens import ApiTokenRepository
from app.modules.api_tokens.dto import CreateApiTokenDto
from app.modules.backups import BackupRepository
from app.modules.backups.dto import CreateBackupRunDto, UpdateBackupSettingsDto
from app.modules.broadcasts import BroadcastRepository
from app.modules.email import record_smtp_failure
from app.modules.event_log import EventOutboxRepository
from app.modules.overview.dto import AttentionItemDto
from app.modules.overview.usecases import GetAttentionUseCase
from app.modules.settings import SettingsRepository
from app.modules.settings.dto import BotStatusDto, UpdateBotSettingsDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.stats_repository import SubscriptionStatsRepository
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.stats_repository import TransactionStatsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.broadcasts.test_repository import save_dto
from tests.modules.overview.test_get_nodes_overview import _node, _NodesStub, _sdk
from tests.modules.overview.test_usecases import _paid_order_dto
from tests.modules.subscriptions.factories import create_subscription

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


@pytest.fixture
async def redis_alive(_clean_redis: None, redis: Redis) -> Redis:
    for process in ("worker", "scheduler"):
        await publish_runtime_heartbeat(redis, process, pid=1, started_at=0.0)
    return redis


def _use_case(
    session: AsyncSession,
    sdk: RemnawaveSDK,
    uow: UnitOfWork,
    settings: SettingsRepository,
    redis: Redis,
) -> GetAttentionUseCase:
    return GetAttentionUseCase(
        sdk,
        TransactionRepository(session),
        TransactionStatsRepository(session),
        BackupRepository(session),
        SubscriptionStatsRepository(session),
        settings,
        BroadcastRepository(session),
        EventOutboxRepository(session),
        ApiTokenRepository(session),
        UserRepository(session),
        redis,
        uow,
    )


async def _seed(
    session: AsyncSession,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    repo = TransactionRepository(session)
    user = await user_repository.create(CreateUserDto(name="Payer", telegram_id=840_001))
    now = datetime_now()
    async with uow:
        failed = [
            await repo.create(
                _paid_order_dto(user_id=user.id, plan_id=plan_id, idempotency_key=f"att-f{i}")
            )
            for i in range(5)
        ]
        stuck = await repo.create(
            _paid_order_dto(user_id=user.id, plan_id=plan_id, idempotency_key="att-p")
        )
        pending = await repo.create(
            _paid_order_dto(user_id=user.id, plan_id=plan_id, idempotency_key="att-s")
        )
    for order in failed:
        await repo.mark_status(order.id, TransactionStatus.FAILED)
    await repo.mark_status(stuck.id, TransactionStatus.PAID)
    await session.execute(
        update(Transaction)
        .where(Transaction.id == stuck.id)
        .values(updated_at=now - timedelta(minutes=20))
    )
    await session.execute(
        update(Transaction)
        .where(Transaction.id == pending.id)
        .values(created_at=now - timedelta(minutes=20), expires_at=now + timedelta(minutes=10))
    )
    backups = BackupRepository(session)
    run = await backups.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
    await backups.mark_failed(run.id, error="boom")
    for n, delta in enumerate((timedelta(hours=10), timedelta(days=3)), start=1):
        await create_subscription(
            subscription_repository,
            user_repository,
            telegram_id=840_100 + n,
            remnawave_user_id=840_100 + n,
            status=SubscriptionStatus.ACTIVE,
            expire_at=now + delta,
        )


async def test_lists_everything_that_needs_attention(
    session: AsyncSession,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    plan_id: int,
    redis_alive: Redis,
) -> None:
    await _seed(session, user_repository, subscription_repository, uow, plan_id)
    sdk = _sdk(_NodesStub([_node("de-1", "DE", connected=False), _node("nl-1", "NL")]))

    result = await _use_case(session, sdk, uow, settings_repository, redis_alive)(OWNER)

    assert [i.kind for i in result.items] == [
        "node_offline",
        "gateway_failures",
        "backup_failed",
        "paid_not_fulfilled",
        "stale_pending",
        "expiring_paid",
    ]
    by_kind = {i.kind: i for i in result.items}
    assert by_kind["node_offline"].subject == "de-1"
    assert by_kind["gateway_failures"].count == 5
    assert by_kind["expiring_paid"].count == 2
    assert by_kind["expiring_paid"].subject == "1"


async def test_admin_without_transactions_view_gets_no_payment_items(
    session: AsyncSession,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    plan_id: int,
    redis_alive: Redis,
) -> None:
    await _seed(session, user_repository, subscription_repository, uow, plan_id)
    actor = OWNER.model_copy(update={"permission_revokes": ["TRANSACTIONS_VIEW"]})

    result = await _use_case(session, _sdk(_NodesStub([])), uow, settings_repository, redis_alive)(
        actor
    )

    kinds = {i.kind for i in result.items}
    assert kinds == {"backup_failed", "expiring_paid"}


async def test_unreachable_panel_drops_only_the_node_items(
    session: AsyncSession,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    plan_id: int,
    redis_alive: Redis,
) -> None:
    await _seed(session, user_repository, subscription_repository, uow, plan_id)
    sdk = _sdk(_NodesStub([], RemnawavePanelUnavailableError("down")))

    result = await _use_case(session, sdk, uow, settings_repository, redis_alive)(OWNER)

    kinds = [i.kind for i in result.items]
    assert "node_offline" not in kinds
    assert "panel_unavailable" in kinds
    assert "gateway_failures" in kinds


async def test_unparsable_panel_response_drops_only_the_node_items(
    session: AsyncSession,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    plan_id: int,
    redis_alive: Redis,
) -> None:
    await _seed(session, user_repository, subscription_repository, uow, plan_id)
    sdk = _sdk(_NodesStub([], ValidationError.from_exception_data("X", [])))

    result = await _use_case(session, sdk, uow, settings_repository, redis_alive)(OWNER)

    kinds = [i.kind for i in result.items]
    assert "node_offline" not in kinds
    assert "panel_unavailable" in kinds
    assert "gateway_failures" in kinds


async def test_transport_error_before_the_breaker_opens_drops_only_the_node_items(
    session: AsyncSession,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    plan_id: int,
    redis_alive: Redis,
) -> None:
    await _seed(session, user_repository, subscription_repository, uow, plan_id)
    sdk = _sdk(_NodesStub([], httpx.ConnectError("down")))

    result = await _use_case(session, sdk, uow, settings_repository, redis_alive)(OWNER)

    kinds = [i.kind for i in result.items]
    assert "node_offline" not in kinds
    assert "panel_unavailable" in kinds
    assert "gateway_failures" in kinds


async def test_stale_pending_counts_only_orders_between_15_and_30_minutes_old(
    session: AsyncSession,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    plan_id: int,
    redis_alive: Redis,
) -> None:
    repo = TransactionRepository(session)
    user = await user_repository.create(CreateUserDto(name="Payer", telegram_id=840_002))
    now = datetime_now()
    async with uow:
        orders = [
            await repo.create(
                _paid_order_dto(user_id=user.id, plan_id=plan_id, idempotency_key=f"sp-{i}")
            )
            for i in range(3)
        ]
    # counted, too fresh, already expired
    for order, age, ttl in zip(orders, (20, 10, 40), (10, 20, -10), strict=True):
        await session.execute(
            update(Transaction)
            .where(Transaction.id == order.id)
            .values(
                created_at=now - timedelta(minutes=age), expires_at=now + timedelta(minutes=ttl)
            )
        )

    result = await _use_case(session, _sdk(_NodesStub([])), uow, settings_repository, redis_alive)(
        OWNER
    )

    assert {i.kind: i.count for i in result.items}["stale_pending"] == 1


async def test_failed_backup_stays_visible_after_a_later_run_of_another_kind(
    session: AsyncSession,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    redis_alive: Redis,
) -> None:
    backups = BackupRepository(session)
    run = await backups.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
    await backups.mark_failed(run.id, error="boom")
    ok = await backups.create_run(CreateBackupRunDto(kind=BackupKind.ASSETS))
    await backups.mark_completed(ok.id, file_path="a", size_bytes=1, checksum_sha256="x")

    result = await _use_case(session, _sdk(_NodesStub([])), uow, settings_repository, redis_alive)(
        OWNER
    )

    failed = [i for i in result.items if i.kind == "backup_failed"]
    assert [i.subject for i in failed] == [BackupKind.DATABASE.value]


async def _configure_bot(settings: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings.update_bot_settings(
            UpdateBotSettingsDto(token="123:abc", secret_token="secret")
        )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (BotStatusDto(is_configured=True, webhook_url="https://x"), False),
        (BotStatusDto(is_configured=True), True),
        (
            BotStatusDto(
                is_configured=True,
                webhook_url="https://x",
                error="old",
                last_error_at=datetime_now() - timedelta(hours=2),
            ),
            False,
        ),
        (
            BotStatusDto(
                is_configured=True,
                webhook_url="https://x",
                error="fresh",
                last_error_at=datetime_now() - timedelta(minutes=5),
            ),
            True,
        ),
        (BotStatusDto(is_configured=True, error="unreachable"), True),
    ],
    ids=["healthy", "no-webhook", "stale-error", "fresh-error", "status-call-failed"],
)
async def test_bot_webhook_item_ignores_a_stale_telegram_error(
    session: AsyncSession,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
    status: BotStatusDto,
    expected: bool,
    redis_alive: Redis,
) -> None:
    await _configure_bot(settings_repository, uow)

    async def _status(token: str, proxy: object) -> BotStatusDto:
        return status

    monkeypatch.setattr("app.modules.overview.usecases.get_attention.fetch_bot_status", _status)

    result = await _use_case(session, _sdk(_NodesStub([])), uow, settings_repository, redis_alive)(
        OWNER
    )

    assert ("bot_webhook" in [i.kind for i in result.items]) is expected


async def _kinds(
    session: AsyncSession, settings: SettingsRepository, uow: UnitOfWork, redis: Redis
) -> dict[str, list[AttentionItemDto]]:
    result = await _use_case(session, _sdk(_NodesStub([])), uow, settings, redis)(OWNER)
    by_kind: dict[str, list[AttentionItemDto]] = {}
    for item in result.items:
        by_kind.setdefault(item.kind, []).append(item)
    return by_kind


async def test_process_without_a_heartbeat_is_down(
    session: AsyncSession, settings_repository: SettingsRepository, uow: UnitOfWork, redis: Redis
) -> None:
    await publish_runtime_heartbeat(redis, "worker", pid=1, started_at=0.0)

    items = await _kinds(session, settings_repository, uow, redis)

    assert [i.subject for i in items["process_down"]] == ["scheduler"]
    assert items["process_down"][0].severity == "critical"


async def test_outbox_entry_waiting_over_five_minutes_is_stuck_unless_poisoned(
    session: AsyncSession,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    redis_alive: Redis,
) -> None:
    now = datetime_now()
    for age, attempts in ((10, 0), (2, 0), (30, 5)):
        session.add(
            EventOutboxEntry(
                category=EventCategory.AUTH,
                event_type="LoginSucceededEvent",
                occurred_at=now - timedelta(minutes=age),
                payload={},
                attempts=attempts,
            )
        )
    await session.flush()

    items = await _kinds(session, settings_repository, uow, redis_alive)

    assert items["outbox_stuck"][0].count == 1


async def test_smtp_failure_is_reported_per_profile(
    session: AsyncSession,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    redis_alive: Redis,
) -> None:
    await record_smtp_failure(redis_alive, bulk=True, at=datetime_now())

    items = await _kinds(session, settings_repository, uow, redis_alive)

    assert [i.subject for i in items["smtp_failed"]] == ["bulk"]


@pytest.mark.parametrize(("hours_ago", "expected"), [(30, True), (20, False)])
async def test_backup_is_overdue_past_its_interval_and_grace(
    session: AsyncSession,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    redis_alive: Redis,
    hours_ago: int,
    expected: bool,
) -> None:
    backups = BackupRepository(session)
    await backups.update_settings(UpdateBackupSettingsDto(enabled=True, interval_hours=24))
    run = await backups.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
    await backups.mark_completed(run.id, file_path="a", size_bytes=1, checksum_sha256="x")
    await session.execute(
        update(BackupRun)
        .where(BackupRun.id == run.id)
        .values(finished_at=datetime_now() - timedelta(hours=hours_ago))
    )

    items = await _kinds(session, settings_repository, uow, redis_alive)

    assert ("backup_overdue" in items) is expected


async def test_failed_and_stalled_broadcasts(
    session: AsyncSession,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    redis_alive: Redis,
) -> None:
    repo = BroadcastRepository(session)
    now = datetime_now()
    # two failed today, one two days ago, sending without progress, sending fine
    cases = (
        ("recent-1", BroadcastStatus.FAILED, timedelta(hours=3)),
        ("recent-2", BroadcastStatus.FAILED, timedelta(hours=1)),
        ("old", BroadcastStatus.FAILED, timedelta(days=2)),
        ("stuck", BroadcastStatus.SENDING, timedelta(minutes=20)),
        (None, BroadcastStatus.SENDING, timedelta(minutes=1)),
    )
    for title, status, age in cases:
        created = await repo.create(save_dto(), created_by=None)
        await session.execute(
            update(Broadcast)
            .where(Broadcast.id == created.id)
            .values(title=title, status=status, updated_at=now - age)
        )

    items = await _kinds(session, settings_repository, uow, redis_alive)

    assert [i.subject for i in items["broadcast_failed"]] == ["recent-2", "recent-1"]
    assert [i.subject for i in items["broadcast_stalled"]] == ["stuck"]


@pytest.mark.parametrize(("refused", "expected"), [(10, True), (9, False)])
async def test_undeliverable_email_only_counts_as_a_spike(
    session: AsyncSession,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    redis_alive: Redis,
    refused: int,
    expected: bool,
) -> None:
    for n in range(refused + 1):
        user = await user_repository.create(CreateUserDto(name=f"U{n}", telegram_id=850_000 + n))
        # the last one was refused too long ago to count
        at = datetime_now() - (timedelta(days=2) if n == refused else timedelta(hours=1))
        await session.execute(
            update(User).where(User.id == user.id).values(email_undeliverable_at=at)
        )

    items = await _kinds(session, settings_repository, uow, redis_alive)

    assert ("email_undeliverable" in items) is expected


async def test_api_token_expiring_within_a_week(
    session: AsyncSession,
    api_token_repository: ApiTokenRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    redis_alive: Redis,
) -> None:
    now = datetime_now()
    cases = (("later", timedelta(days=5)), ("soon", timedelta(days=2)), ("far", timedelta(days=30)))
    for name, expires_in in cases:
        await api_token_repository.create(
            CreateApiTokenDto(
                name=name,
                scopes=["*"],
                token_hash=name * 8,
                created_by_user_id=None,
                expires_at=now + expires_in,
            )
        )
    await api_token_repository.create(
        CreateApiTokenDto(
            name="gone",
            scopes=["*"],
            token_hash="gone" * 8,
            created_by_user_id=None,
            expires_at=now - timedelta(days=1),
        )
    )

    items = await _kinds(session, settings_repository, uow, redis_alive)

    assert [i.subject for i in items["api_token_expiring"]] == ["soon", "later"]
