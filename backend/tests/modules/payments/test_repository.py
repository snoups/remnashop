from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.payment_order import PaymentOrder
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
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
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


async def test_sum_paid_final_price_by_user_ids_groups_by_currency(
    payment_order_repository: PaymentOrderRepository,
    uow: UnitOfWork,
    user_repository: UserRepository,
    plan_id: int,
) -> None:
    buyer_a = await user_repository.create(CreateUserDto(name="a", telegram_id=900_101))
    buyer_b = await user_repository.create(CreateUserDto(name="b", telegram_id=900_102))

    async with uow:
        order_a = await payment_order_repository.create(
            _order_dto(user_id=buyer_a.id, plan_id=plan_id, idempotency_key="sum-a")
        )
        order_b = await payment_order_repository.create(
            _order_dto(user_id=buyer_b.id, plan_id=plan_id, idempotency_key="sum-b")
        )
    await payment_order_repository.mark_status(order_a.id, PaymentOrderStatus.PAID)
    await payment_order_repository.mark_status(order_b.id, PaymentOrderStatus.PAID)

    totals = await payment_order_repository.sum_paid_final_price_by_user_ids(
        [buyer_a.id, buyer_b.id]
    )

    assert totals == {Currency.RUB: Decimal("1000")}


async def test_sum_paid_final_price_by_user_ids_ignores_unpaid_and_unlisted_users(
    payment_order_repository: PaymentOrderRepository,
    uow: UnitOfWork,
    user_repository: UserRepository,
    plan_id: int,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="c", telegram_id=900_103))
    unpaid_buyer = await user_repository.create(CreateUserDto(name="d", telegram_id=900_104))

    async with uow:
        paid = await payment_order_repository.create(
            _order_dto(user_id=buyer.id, plan_id=plan_id, idempotency_key="sum-c")
        )
        await payment_order_repository.create(
            _order_dto(user_id=unpaid_buyer.id, plan_id=plan_id, idempotency_key="sum-d")
        )
    await payment_order_repository.mark_status(paid.id, PaymentOrderStatus.PAID)

    totals = await payment_order_repository.sum_paid_final_price_by_user_ids([buyer.id])

    assert totals == {Currency.RUB: Decimal("500")}


async def test_sum_paid_final_price_by_user_ids_empty_input_returns_empty_dict(
    payment_order_repository: PaymentOrderRepository,
) -> None:
    assert await payment_order_repository.sum_paid_final_price_by_user_ids([]) == {}


async def test_list_user_ids_with_paid_order(
    payment_order_repository: PaymentOrderRepository,
    uow: UnitOfWork,
    user_repository: UserRepository,
    plan_id: int,
) -> None:
    payer = await user_repository.create(CreateUserDto(name="e", telegram_id=900_105))
    non_payer = await user_repository.create(CreateUserDto(name="f", telegram_id=900_106))

    async with uow:
        order = await payment_order_repository.create(
            _order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="paid-e")
        )
    await payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)

    paid_ids = await payment_order_repository.list_user_ids_with_paid_order(
        [payer.id, non_payer.id]
    )

    assert paid_ids == {payer.id}


async def test_user_id_queries_chunk_and_merge_beyond_the_in_param_cap(
    payment_order_repository: PaymentOrderRepository,
    uow: UnitOfWork,
    user_repository: UserRepository,
    plan_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.modules.payments.repository._MAX_IN_PARAMS", 2)

    rub_buyers = [
        await user_repository.create(CreateUserDto(name=f"rub{i}", telegram_id=900_200 + i))
        for i in range(3)
    ]
    usd_buyers = [
        await user_repository.create(CreateUserDto(name=f"usd{i}", telegram_id=900_210 + i))
        for i in range(2)
    ]

    async with uow:
        for i, buyer in enumerate(rub_buyers):
            order = await payment_order_repository.create(
                _order_dto(user_id=buyer.id, plan_id=plan_id, idempotency_key=f"chunk-rub-{i}")
            )
            await payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)
        for i, buyer in enumerate(usd_buyers):
            order = await payment_order_repository.create(
                CreatePaymentOrderDto(
                    **{
                        **_order_dto(
                            user_id=buyer.id, plan_id=plan_id, idempotency_key=f"chunk-usd-{i}"
                        ).__dict__,
                        "currency": Currency.USD,
                        "base_price": Decimal("100"),
                        "final_price": Decimal("100"),
                    }
                )
            )
            await payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)

    all_ids = [b.id for b in rub_buyers + usd_buyers]

    totals = await payment_order_repository.sum_paid_final_price_by_user_ids(all_ids)
    assert totals == {Currency.RUB: Decimal("1500"), Currency.USD: Decimal("200")}

    paid_ids = await payment_order_repository.list_user_ids_with_paid_order(all_ids)
    assert paid_ids == set(all_ids)


async def test_count_paid_since_excludes_pending_and_old_orders(
    payment_order_repository: PaymentOrderRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        old_order = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="count-paid-old")
        )
    await payment_order_repository.mark_status(old_order.id, PaymentOrderStatus.PAID)
    # updated_at is a server default -- Postgres now() is frozen for the
    # whole test transaction, so two rows created moments apart in the same
    # test get an IDENTICAL updated_at. Force the "old" row back in time
    # (same idiom as tests/modules/subscriptions/test_repository.py's
    # test_delete_stale_idempotency_keys_removes_only_old_rows) so `since`
    # below has something real to exclude.
    now = datetime_now()
    await session.execute(
        update(PaymentOrder)
        .where(PaymentOrder.id == old_order.id)
        .values(updated_at=now - timedelta(days=1))
    )
    since = now - timedelta(hours=1)
    async with uow:
        new_paid = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="count-paid-new")
        )
        pending = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="count-paid-pending")
        )
    await payment_order_repository.mark_status(new_paid.id, PaymentOrderStatus.PAID)

    count = await payment_order_repository.count_paid_since(since)

    assert count == 1
    assert pending.status == PaymentOrderStatus.PENDING


async def test_sum_paid_final_price_since_groups_by_currency(
    payment_order_repository: PaymentOrderRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    # A generous past `since` (not datetime_now() captured mid-test) --
    # see the note on Postgres's frozen-per-transaction now() above.
    since = datetime_now() - timedelta(days=1)
    async with uow:
        rub_order = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="sum-rub")
        )
        usd_order_data = _order_dto(
            user_id=user_id, plan_id=plan_id, idempotency_key="sum-usd"
        ).__dict__
        usd_order = await payment_order_repository.create(
            CreatePaymentOrderDto(
                **{
                    **usd_order_data,
                    "currency": Currency.USD,
                    "base_price": Decimal("5"),
                    "final_price": Decimal("5"),
                }
            )
        )
    await payment_order_repository.mark_status(rub_order.id, PaymentOrderStatus.PAID)
    await payment_order_repository.mark_status(usd_order.id, PaymentOrderStatus.PAID)

    totals = await payment_order_repository.sum_paid_final_price_since(since)

    assert totals == {Currency.RUB: Decimal("500"), Currency.USD: Decimal("5")}


async def test_daily_paid_revenue_by_currency_groups_by_day_and_currency(
    payment_order_repository: PaymentOrderRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    since = datetime_now() - timedelta(days=1)
    async with uow:
        order = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="daily-rev")
        )
    await payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)

    daily = await payment_order_repository.daily_paid_revenue_by_currency(since)

    total_revenue = sum(amount for by_currency in daily.values() for amount in by_currency.values())
    assert total_revenue == Decimal("500")


async def test_list_user_ids_with_multiple_paid_orders_requires_more_than_one(
    payment_order_repository: PaymentOrderRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    single_payer = await user_repository.create(CreateUserDto(name="Single", telegram_id=900_101))

    async with uow:
        first = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="multi-1")
        )
        second = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="multi-2")
        )
        only = await payment_order_repository.create(
            _order_dto(user_id=single_payer.id, plan_id=plan_id, idempotency_key="multi-3")
        )
    await payment_order_repository.mark_status(first.id, PaymentOrderStatus.PAID)
    await payment_order_repository.mark_status(second.id, PaymentOrderStatus.PAID)
    await payment_order_repository.mark_status(only.id, PaymentOrderStatus.PAID)

    result = await payment_order_repository.list_user_ids_with_multiple_paid_orders(
        [user_id, single_payer.id]
    )

    assert result == {user_id}


async def test_list_paid_user_month_pairs_dedupes_within_a_month_and_respects_since(
    payment_order_repository: PaymentOrderRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        early_this_month = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="pairs-1")
        )
        later_this_month = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="pairs-2")
        )
        too_old = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="pairs-3")
        )
    await payment_order_repository.mark_status(early_this_month.id, PaymentOrderStatus.PAID)
    await payment_order_repository.mark_status(later_this_month.id, PaymentOrderStatus.PAID)
    await payment_order_repository.mark_status(too_old.id, PaymentOrderStatus.PAID)
    await session.execute(
        update(PaymentOrder)
        .where(PaymentOrder.id == too_old.id)
        .values(updated_at=datetime_now() - timedelta(days=400))
    )

    pairs = await payment_order_repository.list_paid_user_month_pairs(
        [user_id], datetime_now() - timedelta(days=60)
    )

    assert len(pairs) == 1
    result_user_id, month = pairs[0]
    assert result_user_id == user_id
    assert month == datetime_now().date().replace(day=1)
