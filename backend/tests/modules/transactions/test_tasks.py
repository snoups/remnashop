from datetime import timedelta
from decimal import Decimal
from typing import Final
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.exc import OperationalError

from app.core.constants import REDIS_KEY_PREFIX
from app.core.db.models import EventOutboxEntry
from app.core.db.models.transaction import Transaction
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PromocodeRewardType,
    PurchaseChannel,
    PurchaseType,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.exceptions import RetryableTaskError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.promocodes.dto import CreatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.subscriptions import IDEMPOTENCY_KEY_RETENTION_DAYS
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases.purchase_subscription import STALE_CLAIM_AFTER
from app.modules.transactions.dto import CreateTransactionDto, ReconcilePaidTransactionsDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.tasks import confirm_stars_payment_task
from app.modules.transactions.usecases import (
    PruneExpiredTransactionsUseCase,
    ReconcilePaidTransactionsUseCase,
)
from tests.fakes.dispatch import RecordingDispatch
from tests.fakes.events import RecordingEventPublisher
from tests.modules.subscriptions.factories import make_plan_snapshot

_confirm_stars = confirm_stars_payment_task.original_func.__dishka_orig_func__


async def test_prune_expired_transactions_marks_stale_pending_rows_expired(
    transaction_repository: TransactionRepository, user_repository, uow, user_id, plan_id
) -> None:
    async with uow:
        stale = await transaction_repository.create(
            CreateTransactionDto(
                channel=PurchaseChannel.CABINET,
                user_id=user_id,
                plan_id=plan_id,
                plan_snapshot=make_plan_snapshot(plan_id=plan_id),
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                target_subscription_id=None,
                gateway_type=PaymentGatewayType.YOOKASSA,
                base_price=Decimal("500"),
                discount_percent=0,
                discount_source=DiscountSource.NONE,
                final_price=Decimal("500"),
                anchor_base_price=Decimal("500"),
                anchor_final_price=Decimal("500"),
                customer_email=None,
                idempotency_key="stale-key",
                expires_at=datetime_now() - timedelta(minutes=1),
            )
        )

    await PruneExpiredTransactionsUseCase(
        transaction_repository, user_repository, uow, RecordingEventPublisher()
    ).system()

    fetched = await transaction_repository.get_by_id(stale.id)
    assert fetched.status is TransactionStatus.CANCELED


async def test_prune_expired_transactions_publishes_each_expired_order(
    transaction_repository: TransactionRepository, user_repository, uow, user_id, plan_id
) -> None:
    async with uow:
        stale = await transaction_repository.create(
            CreateTransactionDto(
                channel=PurchaseChannel.CABINET,
                user_id=user_id,
                plan_id=plan_id,
                plan_snapshot=make_plan_snapshot(plan_id=plan_id),
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                target_subscription_id=None,
                gateway_type=PaymentGatewayType.YOOKASSA,
                base_price=Decimal("500"),
                discount_percent=0,
                discount_source=DiscountSource.NONE,
                final_price=Decimal("500"),
                anchor_base_price=Decimal("500"),
                anchor_final_price=Decimal("500"),
                customer_email=None,
                idempotency_key="stale-event-key",
                expires_at=datetime_now() - timedelta(minutes=1),
            )
        )
    publisher = RecordingEventPublisher()

    await PruneExpiredTransactionsUseCase(
        transaction_repository, user_repository, uow, publisher
    ).system()

    assert [(e.order_id, e.user_id) for e in publisher.events] == [(stale.id, user_id)]  # type: ignore[attr-defined]


async def test_prune_expired_transactions_gives_back_a_spent_purchase_discount(
    transaction_repository: TransactionRepository, user_repository, uow, user_id, plan_id
) -> None:
    async with uow:
        promocode_id = await _discount_promocode(transaction_repository.session)
        await transaction_repository.create(
            CreateTransactionDto(
                channel=PurchaseChannel.CABINET,
                user_id=user_id,
                plan_id=plan_id,
                plan_snapshot=make_plan_snapshot(plan_id=plan_id),
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                target_subscription_id=None,
                gateway_type=PaymentGatewayType.YOOKASSA,
                base_price=Decimal("500"),
                discount_percent=20,
                discount_source=DiscountSource.PURCHASE,
                discount_promocode_id=promocode_id,
                discount_from_promocode=True,
                final_price=Decimal("400"),
                anchor_base_price=Decimal("500"),
                anchor_final_price=Decimal("400"),
                customer_email=None,
                idempotency_key="stale-discounted-key",
                expires_at=datetime_now() - timedelta(minutes=1),
            )
        )

    await PruneExpiredTransactionsUseCase(
        transaction_repository, user_repository, uow, RecordingEventPublisher()
    ).system()

    assert (await user_repository.find_by_id(user_id)).purchase_discount == 20


async def _prune_discounted_order(
    transaction_repository,
    user_repository,
    uow,
    user_id,
    plan_id,
    *,
    from_promocode: bool,
    key: str,
) -> int:
    async with uow:
        await transaction_repository.create(
            CreateTransactionDto(
                channel=PurchaseChannel.CABINET,
                user_id=user_id,
                plan_id=plan_id,
                plan_snapshot=make_plan_snapshot(plan_id=plan_id),
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                target_subscription_id=None,
                gateway_type=PaymentGatewayType.YOOKASSA,
                base_price=Decimal("500"),
                discount_percent=20,
                discount_source=DiscountSource.PURCHASE,
                discount_from_promocode=from_promocode,
                final_price=Decimal("400"),
                anchor_base_price=Decimal("500"),
                anchor_final_price=Decimal("400"),
                customer_email=None,
                idempotency_key=key,
                expires_at=datetime_now() - timedelta(minutes=1),
            )
        )
    await PruneExpiredTransactionsUseCase(
        transaction_repository, user_repository, uow, RecordingEventPublisher()
    ).system()
    return (await user_repository.find_by_id(user_id)).purchase_discount


async def test_prune_gives_back_an_admin_granted_purchase_discount(
    transaction_repository, user_repository, uow, user_id, plan_id
) -> None:
    restored = await _prune_discounted_order(
        transaction_repository,
        user_repository,
        uow,
        user_id,
        plan_id,
        from_promocode=False,
        key="stale-admin-key",
    )

    assert restored == 20


async def test_prune_keeps_a_deleted_promocodes_discount_gone(
    transaction_repository, user_repository, uow, user_id, plan_id
) -> None:
    restored = await _prune_discounted_order(
        transaction_repository,
        user_repository,
        uow,
        user_id,
        plan_id,
        from_promocode=True,
        key="stale-dead-promo-key",
    )

    assert restored == 0


def _paid_order_dto(*, user_id: int, plan_id: int, idempotency_key: str) -> CreateTransactionDto:
    return CreateTransactionDto(
        channel=PurchaseChannel.CABINET,
        user_id=user_id,
        plan_id=plan_id,
        plan_snapshot=make_plan_snapshot(plan_id=plan_id),
        duration_days=30,
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        target_subscription_id=None,
        gateway_type=PaymentGatewayType.YOOKASSA,
        base_price=Decimal("500"),
        discount_percent=0,
        discount_source=DiscountSource.NONE,
        final_price=Decimal("500"),
        anchor_base_price=Decimal("500"),
        anchor_final_price=Decimal("500"),
        customer_email=None,
        idempotency_key=idempotency_key,
        expires_at=datetime_now() + timedelta(minutes=30),
    )


async def test_reconcile_paid_transactions_redispatches_when_no_subscription_is_linked(
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    uow,
    user_id,
    plan_id,
    idempotency_repository: PurchaseIdempotencyRepository,
    event_publisher: EventPublisher,
    redis: Redis,
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="recon-unlinked")
        )
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)

    dispatch = RecordingDispatch()

    await ReconcilePaidTransactionsUseCase(
        transaction_repository, idempotency_repository, uow, dispatch, event_publisher, redis
    ).system(ReconcilePaidTransactionsDto(grace_period=timedelta(seconds=0)))

    assert len(dispatch.messages) == 1
    assert dispatch.messages[0]["idempotency_key"] == "recon-unlinked"
    assert dispatch.messages[0]["user_id"] == user_id
    assert dispatch.messages[0]["plan_snapshot"]["plan_id"] == plan_id
    assert dispatch.messages[0]["base_price"] == "500.00"


async def test_reconcile_paid_transactions_skips_when_a_subscription_is_already_linked(
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    uow,
    user_id,
    plan_id,
    idempotency_repository: PurchaseIdempotencyRepository,
    event_publisher: EventPublisher,
    redis: Redis,
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="recon-linked")
        )
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
        subscription = await subscription_repository.create(
            CreateSubscriptionDto(
                user_id=user_id,
                remnawave_user_id=555001,
                status=SubscriptionStatus.ACTIVE,
                traffic_limit=100,
                device_limit=3,
                expire_at=datetime_now(),
                url="https://fake-panel.test/sub/555001",
                plan_snapshot=make_plan_snapshot(),
            )
        )
        token = await idempotency_repository.claim("recon-linked", stale_after=STALE_CLAIM_AFTER)
        await idempotency_repository.link("recon-linked", subscription.id, token)

    dispatch = RecordingDispatch()

    await ReconcilePaidTransactionsUseCase(
        transaction_repository, idempotency_repository, uow, dispatch, event_publisher, redis
    ).system(ReconcilePaidTransactionsDto(grace_period=timedelta(seconds=0)))

    assert dispatch.messages == []
    # the link outlives the idempotency key it was read from
    fulfilled = await transaction_repository.get_by_id(order.id)
    assert fulfilled.fulfilled_subscription_id == subscription.id


async def test_reconcile_paid_transactions_ignores_orders_that_are_not_paid(
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    uow,
    user_id,
    plan_id,
    idempotency_repository: PurchaseIdempotencyRepository,
    event_publisher: EventPublisher,
    redis: Redis,
) -> None:
    async with uow:
        await transaction_repository.create(
            _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="recon-pending")
        )

    dispatch = RecordingDispatch()

    await ReconcilePaidTransactionsUseCase(
        transaction_repository, idempotency_repository, uow, dispatch, event_publisher, redis
    ).system(ReconcilePaidTransactionsDto(grace_period=timedelta(seconds=0)))

    assert dispatch.messages == []


async def _create_linked_paid_order(
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    uow,
    *,
    user_id: int,
    plan_id: int,
    idempotency_key: str,
    remnawave_user_id: int,
):
    async with uow:
        order = await transaction_repository.create(
            _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key=idempotency_key)
        )
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
        subscription = await subscription_repository.create(
            CreateSubscriptionDto(
                user_id=user_id,
                remnawave_user_id=remnawave_user_id,
                status=SubscriptionStatus.ACTIVE,
                traffic_limit=100,
                device_limit=3,
                expire_at=datetime_now(),
                url=f"https://fake-panel.test/sub/{remnawave_user_id}",
                plan_snapshot=make_plan_snapshot(),
            )
        )
        idempotency = PurchaseIdempotencyRepository(subscription_repository.session)
        token = await idempotency.claim(idempotency_key, stale_after=STALE_CLAIM_AFTER)
        await idempotency.link(idempotency_key, subscription.id, token)
    return order


async def test_reconcile_paid_transactions_does_not_redispatch_after_idempotency_keys_are_pruned(
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    uow,
    user_id,
    plan_id,
    idempotency_repository: PurchaseIdempotencyRepository,
    event_publisher: EventPublisher,
    redis: Redis,
) -> None:
    await _create_linked_paid_order(
        transaction_repository,
        subscription_repository,
        uow,
        user_id=user_id,
        plan_id=plan_id,
        idempotency_key="recon-pruned",
        remnawave_user_id=555002,
    )

    dispatch = RecordingDispatch()

    await ReconcilePaidTransactionsUseCase(
        transaction_repository, idempotency_repository, uow, dispatch, event_publisher, redis
    ).system(ReconcilePaidTransactionsDto(grace_period=timedelta(seconds=0)))
    async with uow:
        await PurchaseIdempotencyRepository(subscription_repository.session).delete_stale(
            datetime_now() + timedelta(days=1)
        )
    await ReconcilePaidTransactionsUseCase(
        transaction_repository, idempotency_repository, uow, dispatch, event_publisher, redis
    ).system(ReconcilePaidTransactionsDto(grace_period=timedelta(seconds=0)))

    assert dispatch.messages == []


async def test_reconcile_paid_transactions_skips_orders_older_than_the_idempotency_retention(
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    session,
    uow,
    user_id,
    plan_id,
    idempotency_repository: PurchaseIdempotencyRepository,
    event_publisher: EventPublisher,
    redis: Redis,
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="recon-too-old")
        )
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
    await session.execute(
        update(Transaction)
        .where(Transaction.id == order.id)
        .values(updated_at=datetime_now() - timedelta(days=IDEMPOTENCY_KEY_RETENTION_DAYS))
    )

    dispatch = RecordingDispatch()

    await ReconcilePaidTransactionsUseCase(
        transaction_repository, idempotency_repository, uow, dispatch, event_publisher, redis
    ).system(ReconcilePaidTransactionsDto(grace_period=timedelta(seconds=0)))

    assert dispatch.messages == []


async def _discount_promocode(session) -> int:
    # a restored discount needs the promocode it came from
    promo = await PromocodeRepository(session).create(
        CreatePromocodeDto(
            code="RESTOREME", reward_type=PromocodeRewardType.PURCHASE_DISCOUNT, reward=20
        )
    )
    return promo.id


def test_confirm_stars_payment_task_is_retry_enabled() -> None:
    assert confirm_stars_payment_task.labels.get("retry_on_error") is True
    assert confirm_stars_payment_task.labels.get("max_retries") == 3


_STARS_ARGS: Final[dict[str, object]] = {
    "telegram_id": 1,
    "payload": "ref",
    "currency": "XTR",
    "total_amount": 50,
    "charge_id": "charge",
}


@pytest.mark.parametrize(
    "error", [OperationalError("SELECT 1", {}, Exception("down")), ConnectionRefusedError()]
)
async def test_confirm_stars_payment_task_retries_transient_failures(error: Exception) -> None:
    use_case = AsyncMock()
    use_case.system.side_effect = error

    with pytest.raises(RetryableTaskError):
        await _confirm_stars(**_STARS_ARGS, use_case=use_case)


async def test_confirm_stars_payment_task_does_not_retry_bugs() -> None:
    use_case = AsyncMock()
    use_case.system.side_effect = ValueError("bug")

    with pytest.raises(ValueError):
        await _confirm_stars(**_STARS_ARGS, use_case=use_case)


async def test_a_stuck_paid_order_is_reported_once_across_sweeps(
    transaction_repository: TransactionRepository,
    uow,
    user_id,
    plan_id,
    idempotency_repository: PurchaseIdempotencyRepository,
    event_publisher: EventPublisher,
    redis: Redis,
    session,
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key=str(uuid4()))
        )
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
    await redis.delete(f"{REDIS_KEY_PREFIX}paid_not_fulfilled_reported:{order.id}")
    use_case = ReconcilePaidTransactionsUseCase(
        transaction_repository,
        idempotency_repository,
        uow,
        RecordingDispatch(),
        event_publisher,
        redis,
    )

    for _ in range(2):
        await use_case.system(ReconcilePaidTransactionsDto(grace_period=timedelta(seconds=0)))

    reported = await session.scalar(
        select(func.count()).where(
            EventOutboxEntry.event_type == "PaidOrderNotFulfilledEvent",
            EventOutboxEntry.payload["order_id"].astext == str(order.id),
        )
    )
    assert reported == 1
