from datetime import timedelta
from decimal import Decimal

from sqlalchemy import update

import app.modules.transactions.tasks as tasks_module
from app.core.db.models.transaction import Transaction
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseType,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.utils.time import datetime_now
from app.modules.subscriptions import IDEMPOTENCY_KEY_RETENTION_DAYS
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.tasks import prune_expired_transactions, reconcile_paid_transactions
from tests.modules.subscriptions.factories import make_plan_snapshot


async def test_prune_expired_transactions_marks_stale_pending_rows_expired(
    transaction_repository: TransactionRepository, user_repository, uow, user_id, plan_id
) -> None:
    async with uow:
        stale = await transaction_repository.create(
            CreateTransactionDto(
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
                customer_email=None,
                idempotency_key="stale-key",
                expires_at=datetime_now() - timedelta(minutes=1),
            )
        )

    await prune_expired_transactions(
        transaction_repository=transaction_repository,
        user_repository=user_repository,
        uow=uow,
    )

    fetched = await transaction_repository.get_by_id(stale.id)
    assert fetched.status is TransactionStatus.CANCELED


async def test_prune_expired_transactions_gives_back_a_spent_purchase_discount(
    transaction_repository: TransactionRepository, user_repository, uow, user_id, plan_id
) -> None:
    async with uow:
        await transaction_repository.create(
            CreateTransactionDto(
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
                final_price=Decimal("400"),
                customer_email=None,
                idempotency_key="stale-discounted-key",
                expires_at=datetime_now() - timedelta(minutes=1),
            )
        )

    await prune_expired_transactions(
        transaction_repository=transaction_repository,
        user_repository=user_repository,
        uow=uow,
    )

    assert (await user_repository.get_by_id(user_id)).purchase_discount == 20


def _paid_order_dto(*, user_id: int, plan_id: int, idempotency_key: str) -> CreateTransactionDto:
    return CreateTransactionDto(
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
    monkeypatch,
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="recon-unlinked")
        )
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)

    dispatched: list[dict[str, object]] = []

    async def _fake_kiq(**kwargs: object) -> None:
        dispatched.append(kwargs)

    monkeypatch.setattr(tasks_module.purchase_subscription_task, "kiq", _fake_kiq)

    await reconcile_paid_transactions(
        transaction_repository=transaction_repository,
        subscription_repository=subscription_repository,
        uow=uow,
        grace_period=timedelta(seconds=0),
    )

    assert len(dispatched) == 1
    assert dispatched[0]["idempotency_key"] == "recon-unlinked"
    assert dispatched[0]["user_id"] == user_id
    assert dispatched[0]["plan_snapshot"]["plan_id"] == plan_id
    assert dispatched[0]["base_price"] == "500.00"


async def test_reconcile_paid_transactions_skips_when_a_subscription_is_already_linked(
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    uow,
    user_id,
    plan_id,
    monkeypatch,
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
        await subscription_repository.claim_idempotency_key("recon-linked")
        await subscription_repository.link_idempotency_key("recon-linked", subscription.id)

    dispatched: list[dict[str, object]] = []

    async def _fake_kiq(**kwargs: object) -> None:
        dispatched.append(kwargs)

    monkeypatch.setattr(tasks_module.purchase_subscription_task, "kiq", _fake_kiq)

    await reconcile_paid_transactions(
        transaction_repository=transaction_repository,
        subscription_repository=subscription_repository,
        uow=uow,
        grace_period=timedelta(seconds=0),
    )

    assert dispatched == []


async def test_reconcile_paid_transactions_ignores_orders_that_are_not_paid(
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    uow,
    user_id,
    plan_id,
    monkeypatch,
) -> None:
    async with uow:
        await transaction_repository.create(
            _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="recon-pending")
        )

    dispatched: list[dict[str, object]] = []

    async def _fake_kiq(**kwargs: object) -> None:
        dispatched.append(kwargs)

    monkeypatch.setattr(tasks_module.purchase_subscription_task, "kiq", _fake_kiq)

    await reconcile_paid_transactions(
        transaction_repository=transaction_repository,
        subscription_repository=subscription_repository,
        uow=uow,
        grace_period=timedelta(seconds=0),
    )

    assert dispatched == []


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
        await subscription_repository.claim_idempotency_key(idempotency_key)
        await subscription_repository.link_idempotency_key(idempotency_key, subscription.id)
    return order


async def test_reconcile_paid_transactions_does_not_redispatch_after_idempotency_keys_are_pruned(
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    uow,
    user_id,
    plan_id,
    monkeypatch,
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

    dispatched: list[dict[str, object]] = []

    async def _fake_kiq(**kwargs: object) -> None:
        dispatched.append(kwargs)

    monkeypatch.setattr(tasks_module.purchase_subscription_task, "kiq", _fake_kiq)

    await reconcile_paid_transactions(
        transaction_repository=transaction_repository,
        subscription_repository=subscription_repository,
        uow=uow,
        grace_period=timedelta(seconds=0),
    )
    async with uow:
        await subscription_repository.delete_stale_idempotency_keys(
            datetime_now() + timedelta(days=1)
        )
    await reconcile_paid_transactions(
        transaction_repository=transaction_repository,
        subscription_repository=subscription_repository,
        uow=uow,
        grace_period=timedelta(seconds=0),
    )

    assert dispatched == []


async def test_reconcile_paid_transactions_skips_orders_older_than_the_idempotency_retention(
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    session,
    uow,
    user_id,
    plan_id,
    monkeypatch,
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

    dispatched: list[dict[str, object]] = []

    async def _fake_kiq(**kwargs: object) -> None:
        dispatched.append(kwargs)

    monkeypatch.setattr(tasks_module.purchase_subscription_task, "kiq", _fake_kiq)

    await reconcile_paid_transactions(
        transaction_repository=transaction_repository,
        subscription_repository=subscription_repository,
        uow=uow,
        grace_period=timedelta(seconds=0),
    )

    assert dispatched == []
