from datetime import timedelta

import httpx
import pytest
from pydantic import ValidationError
from remnapy import RemnawaveSDK
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.transaction import Transaction
from app.core.db.uow import UnitOfWork
from app.core.enums import BackupKind, Locale, Role, SubscriptionStatus, TransactionStatus
from app.core.exceptions import RemnawavePanelUnavailableError
from app.core.utils.time import datetime_now
from app.modules.backups import BackupRepository
from app.modules.backups.dto import CreateBackupRunDto
from app.modules.overview.usecases import GetAttentionUseCase
from app.modules.settings import SettingsRepository
from app.modules.settings.dto import BotStatusDto, UpdateBotSettingsDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.stats_repository import SubscriptionStatsRepository
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.stats_repository import TransactionStatsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.overview.test_get_nodes_overview import _node, _NodesStub, _sdk
from tests.modules.overview.test_usecases import _paid_order_dto
from tests.modules.subscriptions.factories import create_subscription

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


def _use_case(
    session: AsyncSession, sdk: RemnawaveSDK, uow: UnitOfWork, settings: SettingsRepository
) -> GetAttentionUseCase:
    return GetAttentionUseCase(
        sdk,
        TransactionRepository(session),
        TransactionStatsRepository(session),
        BackupRepository(session),
        SubscriptionStatsRepository(session),
        settings,
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
) -> None:
    await _seed(session, user_repository, subscription_repository, uow, plan_id)
    sdk = _sdk(_NodesStub([_node("de-1", "DE", connected=False), _node("nl-1", "NL")]))

    result = await _use_case(session, sdk, uow, settings_repository)(OWNER)

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
) -> None:
    await _seed(session, user_repository, subscription_repository, uow, plan_id)
    actor = OWNER.model_copy(update={"permission_revokes": ["TRANSACTIONS_VIEW"]})

    result = await _use_case(session, _sdk(_NodesStub([])), uow, settings_repository)(actor)

    kinds = {i.kind for i in result.items}
    assert kinds == {"backup_failed", "expiring_paid"}


async def test_unreachable_panel_drops_only_the_node_items(
    session: AsyncSession,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    await _seed(session, user_repository, subscription_repository, uow, plan_id)
    sdk = _sdk(_NodesStub([], RemnawavePanelUnavailableError("down")))

    result = await _use_case(session, sdk, uow, settings_repository)(OWNER)

    kinds = [i.kind for i in result.items]
    assert "node_offline" not in kinds
    assert "gateway_failures" in kinds


async def test_unparsable_panel_response_drops_only_the_node_items(
    session: AsyncSession,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    await _seed(session, user_repository, subscription_repository, uow, plan_id)
    sdk = _sdk(_NodesStub([], ValidationError.from_exception_data("X", [])))

    result = await _use_case(session, sdk, uow, settings_repository)(OWNER)

    kinds = [i.kind for i in result.items]
    assert "node_offline" not in kinds
    assert "gateway_failures" in kinds


async def test_transport_error_before_the_breaker_opens_drops_only_the_node_items(
    session: AsyncSession,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    await _seed(session, user_repository, subscription_repository, uow, plan_id)
    sdk = _sdk(_NodesStub([], httpx.ConnectError("down")))

    result = await _use_case(session, sdk, uow, settings_repository)(OWNER)

    kinds = [i.kind for i in result.items]
    assert "node_offline" not in kinds
    assert "gateway_failures" in kinds


async def test_stale_pending_counts_only_orders_between_15_and_30_minutes_old(
    session: AsyncSession,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    plan_id: int,
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

    result = await _use_case(session, _sdk(_NodesStub([])), uow, settings_repository)(OWNER)

    assert {i.kind: i.count for i in result.items}["stale_pending"] == 1


async def test_failed_backup_stays_visible_after_a_later_run_of_another_kind(
    session: AsyncSession,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    backups = BackupRepository(session)
    run = await backups.create_run(CreateBackupRunDto(kind=BackupKind.DATABASE))
    await backups.mark_failed(run.id, error="boom")
    ok = await backups.create_run(CreateBackupRunDto(kind=BackupKind.ASSETS))
    await backups.mark_completed(ok.id, file_path="a", size_bytes=1, checksum_sha256="x")

    result = await _use_case(session, _sdk(_NodesStub([])), uow, settings_repository)(OWNER)

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
) -> None:
    await _configure_bot(settings_repository, uow)

    async def _status(token: str, proxy: object) -> BotStatusDto:
        return status

    monkeypatch.setattr("app.modules.overview.usecases.get_attention.fetch_bot_status", _status)

    result = await _use_case(session, _sdk(_NodesStub([])), uow, settings_repository)(OWNER)

    assert ("bot_webhook" in [i.kind for i in result.items]) is expected
