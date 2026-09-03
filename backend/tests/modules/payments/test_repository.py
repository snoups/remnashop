from datetime import timedelta
from decimal import Decimal

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PaymentOrderStatus,
    PurchaseType,
)
from app.core.utils.time import datetime_now
from app.modules.payments.dto import CreatePaymentOrderDto
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.plans.repository import PlanRepository
from tests.modules.subscriptions.factories import make_plan_snapshot


def _order_dto(*, user_id: int, plan_id: int, idempotency_key: str) -> CreatePaymentOrderDto:
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


async def test_create_and_get_by_id(
    payment_order_repository: PaymentOrderRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        created = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-1")
        )

    fetched = await payment_order_repository.get_by_id(created.id)
    assert fetched.status is PaymentOrderStatus.PENDING
    assert fetched.final_price == Decimal("500")
    assert fetched.plan_snapshot.plan_id == plan_id
    assert fetched.plan_snapshot.name == "Basic"


async def test_plan_deletion_nulls_plan_id_but_keeps_the_snapshot(
    payment_order_repository: PaymentOrderRepository,
    plan_repository: PlanRepository,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    # purchase_subscription_task provisions entirely from plan_snapshot
    # (captured at checkout time) -- it never re-resolves plan_id via
    # PlanRepository, even for a PAID order still awaiting provisioning. So
    # deleting the plan is safe: plan_id is SET NULL, plan_snapshot survives
    # as the durable record of what was actually ordered.
    async with uow:
        created = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-snapshot")
        )
        await payment_order_repository.mark_status(created.id, PaymentOrderStatus.PAID)

    await plan_repository.delete(plan_id)

    fetched = await payment_order_repository.get_by_id(created.id)
    assert fetched.plan_id is None
    assert fetched.plan_snapshot.plan_id == plan_id


async def test_get_by_idempotency_key(
    payment_order_repository: PaymentOrderRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        created = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-2")
        )

    found = await payment_order_repository.get_by_idempotency_key("key-2")
    assert found is not None
    assert found.id == created.id

    assert await payment_order_repository.get_by_idempotency_key("nonexistent") is None


async def test_mark_paid_sets_external_payment_id_and_status(
    payment_order_repository: PaymentOrderRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        created = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-3")
        )
        await payment_order_repository.mark_status(
            created.id, PaymentOrderStatus.PAID, external_payment_id="yk-123"
        )

    fetched = await payment_order_repository.get_by_id(created.id)
    assert fetched.status is PaymentOrderStatus.PAID
    assert fetched.external_payment_id == "yk-123"


async def test_get_by_external_payment_id(
    payment_order_repository: PaymentOrderRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        created = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-4")
        )
        await payment_order_repository.mark_status(
            created.id, PaymentOrderStatus.PENDING, external_payment_id="yk-456"
        )

    found = await payment_order_repository.get_by_external_payment_id("yk-456")
    assert found is not None
    assert found.id == created.id


async def test_list_expired_pending(
    payment_order_repository: PaymentOrderRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        expired_pending = await payment_order_repository.create(
            CreatePaymentOrderDto(
                **{
                    **_order_dto(
                        user_id=user_id, plan_id=plan_id, idempotency_key="key-expired-pending"
                    ).__dict__,
                    "expires_at": datetime_now() - timedelta(minutes=1),
                }
            )
        )
        await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-future-pending")
        )
        expired_paid = await payment_order_repository.create(
            CreatePaymentOrderDto(
                **{
                    **_order_dto(
                        user_id=user_id, plan_id=plan_id, idempotency_key="key-expired-paid"
                    ).__dict__,
                    "expires_at": datetime_now() - timedelta(minutes=1),
                }
            )
        )
        await payment_order_repository.mark_status(expired_paid.id, PaymentOrderStatus.PAID)

    expired = await payment_order_repository.list_expired_pending(datetime_now())
    assert [order.id for order in expired] == [expired_pending.id]
    assert expired[0].idempotency_key == "key-expired-pending"


async def test_list_paid_awaiting_reconciliation_only_returns_paid_orders(
    payment_order_repository: PaymentOrderRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        paid = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-recon-paid")
        )
        await payment_order_repository.mark_status(paid.id, PaymentOrderStatus.PAID)
        await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-recon-pending")
        )

    awaiting = await payment_order_repository.list_paid_awaiting_reconciliation(datetime_now())
    assert [order.id for order in awaiting] == [paid.id]


async def test_list_paid_awaiting_reconciliation_excludes_orders_paid_too_recently(
    payment_order_repository: PaymentOrderRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        paid = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-recon-fresh")
        )
        await payment_order_repository.mark_status(paid.id, PaymentOrderStatus.PAID)

    # A cutoff before this order was even created -- its updated_at is after
    # the cutoff, so it hasn't cleared the grace period yet.
    cutoff = datetime_now() - timedelta(minutes=5)
    awaiting = await payment_order_repository.list_paid_awaiting_reconciliation(cutoff)
    assert paid.id not in [order.id for order in awaiting]


async def test_list_paginated_filters_by_status(
    payment_order_repository: PaymentOrderRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        pending = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-page-pending")
        )
        paid = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-page-paid")
        )
        await payment_order_repository.mark_status(paid.id, PaymentOrderStatus.PAID)

    orders, total = await payment_order_repository.list_paginated(
        status=PaymentOrderStatus.PAID, page=1, page_size=50
    )
    assert total == 1
    assert [order.id for order in orders] == [paid.id]

    orders, total = await payment_order_repository.list_paginated(status=None, page=1, page_size=50)
    ids = {order.id for order in orders}
    assert pending.id in ids
    assert paid.id in ids
    assert total >= 2


async def test_mark_expired_pending_only_touches_expired_pending_rows(
    payment_order_repository: PaymentOrderRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        expired_pending = await payment_order_repository.create(
            CreatePaymentOrderDto(
                **{
                    **_order_dto(
                        user_id=user_id, plan_id=plan_id, idempotency_key="key-bulk-expired"
                    ).__dict__,
                    "expires_at": datetime_now() - timedelta(minutes=1),
                }
            )
        )
        future_pending = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-bulk-future")
        )
        expired_paid = await payment_order_repository.create(
            CreatePaymentOrderDto(
                **{
                    **_order_dto(
                        user_id=user_id, plan_id=plan_id, idempotency_key="key-bulk-paid"
                    ).__dict__,
                    "expires_at": datetime_now() - timedelta(minutes=1),
                }
            )
        )
        await payment_order_repository.mark_status(expired_paid.id, PaymentOrderStatus.PAID)

        marked = await payment_order_repository.mark_expired_pending(datetime_now())

    assert marked == 1
    assert (await payment_order_repository.get_by_id(expired_pending.id)).status == (
        PaymentOrderStatus.EXPIRED
    )
    assert (await payment_order_repository.get_by_id(future_pending.id)).status == (
        PaymentOrderStatus.PENDING
    )
    assert (await payment_order_repository.get_by_id(expired_paid.id)).status == (
        PaymentOrderStatus.PAID
    )
