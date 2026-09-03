from datetime import timedelta
from decimal import Decimal

import app.modules.payments.tasks as tasks_module
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PaymentOrderStatus,
    PurchaseType,
    SubscriptionStatus,
)
from app.core.utils.time import datetime_now
from app.modules.payments.dto import CreatePaymentOrderDto
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.payments.tasks import prune_expired_payment_orders, reconcile_paid_orders
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from tests.modules.subscriptions.factories import make_plan_snapshot


async def test_prune_expired_payment_orders_marks_stale_pending_rows_expired(
    payment_order_repository: PaymentOrderRepository, uow, user_id, plan_id
) -> None:
    async with uow:
        stale = await payment_order_repository.create(
            CreatePaymentOrderDto(
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

    await prune_expired_payment_orders(payment_order_repository=payment_order_repository, uow=uow)

    fetched = await payment_order_repository.get_by_id(stale.id)
    assert fetched.status is PaymentOrderStatus.EXPIRED


def _paid_order_dto(*, user_id: int, plan_id: int, idempotency_key: str) -> CreatePaymentOrderDto:
    return CreatePaymentOrderDto(
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


async def test_reconcile_paid_orders_redispatches_when_no_subscription_is_linked(
    payment_order_repository: PaymentOrderRepository,
    subscription_repository: SubscriptionRepository,
    uow,
    user_id,
    plan_id,
    monkeypatch,
) -> None:
    async with uow:
        order = await payment_order_repository.create(
            _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="recon-unlinked")
        )
        await payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)

    dispatched: list[dict[str, object]] = []

    async def _fake_kiq(**kwargs: object) -> None:
        dispatched.append(kwargs)

    monkeypatch.setattr(tasks_module.purchase_subscription_task, "kiq", _fake_kiq)

    await reconcile_paid_orders(
        payment_order_repository=payment_order_repository,
        subscription_repository=subscription_repository,
        grace_period=timedelta(seconds=0),
    )

    assert len(dispatched) == 1
    assert dispatched[0]["idempotency_key"] == "recon-unlinked"
    assert dispatched[0]["user_id"] == user_id
    assert dispatched[0]["plan_snapshot"]["plan_id"] == plan_id


async def test_reconcile_paid_orders_skips_when_a_subscription_is_already_linked(
    payment_order_repository: PaymentOrderRepository,
    subscription_repository: SubscriptionRepository,
    uow,
    user_id,
    plan_id,
    monkeypatch,
) -> None:
    async with uow:
        order = await payment_order_repository.create(
            _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="recon-linked")
        )
        await payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)
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

    await reconcile_paid_orders(
        payment_order_repository=payment_order_repository,
        subscription_repository=subscription_repository,
        grace_period=timedelta(seconds=0),
    )

    assert dispatched == []


async def test_reconcile_paid_orders_ignores_orders_that_are_not_paid(
    payment_order_repository: PaymentOrderRepository,
    subscription_repository: SubscriptionRepository,
    uow,
    user_id,
    plan_id,
    monkeypatch,
) -> None:
    async with uow:
        await payment_order_repository.create(
            _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="recon-pending")
        )

    dispatched: list[dict[str, object]] = []

    async def _fake_kiq(**kwargs: object) -> None:
        dispatched.append(kwargs)

    monkeypatch.setattr(tasks_module.purchase_subscription_task, "kiq", _fake_kiq)

    await reconcile_paid_orders(
        payment_order_repository=payment_order_repository,
        subscription_repository=subscription_repository,
        grace_period=timedelta(seconds=0),
    )

    assert dispatched == []
