from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.transaction import Transaction
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseType,
    TransactionStatus,
)
from app.core.utils.time import datetime_now
from app.modules.plans.repository import PlanRepository
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot


def _order_dto(*, user_id: int, plan_id: int, idempotency_key: str) -> CreateTransactionDto:
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


async def test_create_and_get_by_id(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        created = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-1")
        )

    fetched = await transaction_repository.get_by_id(created.id)
    assert fetched.status is TransactionStatus.PENDING
    assert fetched.final_price == Decimal("500")
    assert fetched.plan_snapshot.plan_id == plan_id
    assert fetched.plan_snapshot.name == "Basic"


async def test_plan_deletion_nulls_plan_id_but_keeps_the_snapshot(
    transaction_repository: TransactionRepository,
    plan_repository: PlanRepository,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    # purchase_subscription_task provisions from plan_snapshot alone, even for
    # a PAID order not yet provisioned, so deleting the plan is safe
    async with uow:
        created = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-snapshot")
        )
        await transaction_repository.mark_status(created.id, TransactionStatus.PAID)

    await plan_repository.delete(plan_id)

    fetched = await transaction_repository.get_by_id(created.id)
    assert fetched.plan_id is None
    assert fetched.plan_snapshot.plan_id == plan_id


async def test_get_by_idempotency_key(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        created = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-2")
        )

    found = await transaction_repository.get_by_idempotency_key("key-2")
    assert found is not None
    assert found.id == created.id

    assert await transaction_repository.get_by_idempotency_key("nonexistent") is None


async def test_mark_paid_sets_external_payment_id_and_status(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        created = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-3")
        )
        await transaction_repository.mark_status(
            created.id, TransactionStatus.PAID, external_payment_id="yk-123"
        )

    fetched = await transaction_repository.get_by_id(created.id)
    assert fetched.status is TransactionStatus.PAID
    assert fetched.external_payment_id == "yk-123"


async def test_get_by_external_payment_id(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        created = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-4")
        )
        await transaction_repository.mark_status(
            created.id, TransactionStatus.PENDING, external_payment_id="yk-456"
        )

    found = await transaction_repository.get_by_external_payment_id("yk-456")
    assert found is not None
    assert found.id == created.id


async def test_list_paid_awaiting_reconciliation_only_returns_paid_orders(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        paid = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-recon-paid")
        )
        await transaction_repository.mark_status(paid.id, TransactionStatus.PAID)
        await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-recon-pending")
        )

    awaiting = await transaction_repository.list_paid_awaiting_reconciliation(
        datetime_now(), since=datetime_now() - timedelta(days=1)
    )
    assert [order.id for order in awaiting] == [paid.id]


async def test_list_paid_awaiting_reconciliation_excludes_orders_paid_too_recently(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        paid = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-recon-fresh")
        )
        await transaction_repository.mark_status(paid.id, TransactionStatus.PAID)

    # the cutoff precedes the order, so it's still inside the grace period
    cutoff = datetime_now() - timedelta(minutes=5)
    awaiting = await transaction_repository.list_paid_awaiting_reconciliation(
        cutoff, since=cutoff - timedelta(days=1)
    )
    assert paid.id not in [order.id for order in awaiting]


async def test_list_paid_awaiting_reconciliation_excludes_fulfilled_orders(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        paid = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-recon-fulfilled")
        )
        paid = await transaction_repository.mark_status(paid.id, TransactionStatus.PAID)
        await transaction_repository.mark_fulfilled(paid.id)

    fetched = await transaction_repository.get_by_id(paid.id)
    # updated_at drives revenue-by-day analytics, fulfilment must not move it
    assert fetched.updated_at == paid.updated_at

    awaiting = await transaction_repository.list_paid_awaiting_reconciliation(
        datetime_now(), since=datetime_now() - timedelta(days=1)
    )
    assert paid.id not in [order.id for order in awaiting]


async def test_list_paid_awaiting_reconciliation_excludes_orders_before_since(
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        paid = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-recon-old")
        )
        await transaction_repository.mark_status(paid.id, TransactionStatus.PAID)
    await session.execute(
        update(Transaction)
        .where(Transaction.id == paid.id)
        .values(updated_at=datetime_now() - timedelta(days=10))
    )

    awaiting = await transaction_repository.list_paid_awaiting_reconciliation(
        datetime_now(), since=datetime_now() - timedelta(days=6)
    )
    assert paid.id not in [order.id for order in awaiting]


async def test_list_paginated_filters_by_status(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        pending = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-page-pending")
        )
        paid = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-page-paid")
        )
        await transaction_repository.mark_status(paid.id, TransactionStatus.PAID)

    orders, total = await transaction_repository.list_paginated(
        status=TransactionStatus.PAID, page=1, page_size=50
    )
    assert total == 1
    assert [order.id for order in orders] == [paid.id]

    orders, total = await transaction_repository.list_paginated(status=None, page=1, page_size=50)
    ids = {order.id for order in orders}
    assert pending.id in ids
    assert paid.id in ids
    assert total >= 2


async def test_summarize_groups_by_status_and_currency_and_honours_filters(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-sum-pending")
        )
        paid_ids = []
        for key in ("key-sum-paid-1", "key-sum-paid-2"):
            order = await transaction_repository.create(
                _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key=key)
            )
            paid_ids.append(order.id)
    for order_id in paid_ids:
        await transaction_repository.mark_status(order_id, TransactionStatus.PAID)

    rows = await transaction_repository.summarize()
    assert (TransactionStatus.PAID, Currency.RUB, 2, Decimal("1000"), Decimal("1000")) in rows
    assert (TransactionStatus.PENDING, Currency.RUB, 1, Decimal("500"), Decimal("500")) in rows

    rows = await transaction_repository.summarize(status=TransactionStatus.PAID)
    assert rows == [(TransactionStatus.PAID, Currency.RUB, 2, Decimal("1000"), Decimal("1000"))]


async def test_list_paginated_filters_by_gateway_purchase_type_and_created_from(
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        stars_renew = await transaction_repository.create(
            CreateTransactionDto(
                **{
                    **_order_dto(
                        user_id=user_id, plan_id=plan_id, idempotency_key="key-filter-stars"
                    ).__dict__,
                    "gateway_type": PaymentGatewayType.TELEGRAM_STARS,
                    "purchase_type": PurchaseType.RENEW,
                }
            )
        )
        old_yookassa = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-filter-old")
        )
    now = datetime_now()
    await session.execute(
        update(Transaction)
        .where(Transaction.id == old_yookassa.id)
        .values(created_at=now - timedelta(days=40))
    )

    by_gateway, _ = await transaction_repository.list_paginated(
        gateway_type=PaymentGatewayType.TELEGRAM_STARS
    )
    assert [order.id for order in by_gateway] == [stars_renew.id]

    by_type, _ = await transaction_repository.list_paginated(purchase_type=PurchaseType.RENEW)
    assert [order.id for order in by_type] == [stars_renew.id]

    recent, _ = await transaction_repository.list_paginated(created_from=now - timedelta(days=30))
    recent_ids = {order.id for order in recent}
    assert stars_renew.id in recent_ids
    assert old_yookassa.id not in recent_ids


async def test_list_gateway_types_returns_distinct_non_test_gateways(
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        for key in ("gw-1", "gw-2"):
            await transaction_repository.create(
                _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key=key)
            )
        test_order = await transaction_repository.create(
            CreateTransactionDto(
                **{
                    **_order_dto(
                        user_id=user_id, plan_id=plan_id, idempotency_key="gw-test"
                    ).__dict__,
                    "gateway_type": PaymentGatewayType.HELEKET,
                }
            )
        )
    await session.execute(
        update(Transaction).where(Transaction.id == test_order.id).values(is_test=True)
    )

    assert await transaction_repository.list_gateway_types() == [PaymentGatewayType.YOOKASSA]


async def test_list_paginated_search_matches_id_and_user_id(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-search")
        )

    by_id, _ = await transaction_repository.list_paginated(search=str(order.id))
    assert order.id in [item.id for item in by_id]

    none, total = await transaction_repository.list_paginated(search="no-such-order-zzz")
    assert (none, total) == ([], 0)

    huge, _ = await transaction_repository.list_paginated(search="9" * 30)
    assert huge == []


async def test_cancel_expired_pending_only_touches_expired_pending_rows(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        expired_pending = await transaction_repository.create(
            CreateTransactionDto(
                **{
                    **_order_dto(
                        user_id=user_id, plan_id=plan_id, idempotency_key="key-bulk-expired"
                    ).__dict__,
                    "expires_at": datetime_now() - timedelta(minutes=1),
                }
            )
        )
        future_pending = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-bulk-future")
        )
        expired_paid = await transaction_repository.create(
            CreateTransactionDto(
                **{
                    **_order_dto(
                        user_id=user_id, plan_id=plan_id, idempotency_key="key-bulk-paid"
                    ).__dict__,
                    "expires_at": datetime_now() - timedelta(minutes=1),
                }
            )
        )
        await transaction_repository.mark_status(expired_paid.id, TransactionStatus.PAID)

        marked = await transaction_repository.cancel_expired_pending(datetime_now())

    assert [order.id for order in marked] == [expired_pending.id]
    assert (await transaction_repository.get_by_id(expired_pending.id)).status == (
        TransactionStatus.CANCELED
    )
    assert (await transaction_repository.get_by_id(future_pending.id)).status == (
        TransactionStatus.PENDING
    )
    assert (await transaction_repository.get_by_id(expired_paid.id)).status == (
        TransactionStatus.PAID
    )


async def test_sum_paid_final_price_by_user_ids_groups_by_currency(
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
    user_repository: UserRepository,
    plan_id: int,
) -> None:
    buyer_a = await user_repository.create(CreateUserDto(name="a", telegram_id=900_101))
    buyer_b = await user_repository.create(CreateUserDto(name="b", telegram_id=900_102))

    async with uow:
        order_a = await transaction_repository.create(
            _order_dto(user_id=buyer_a.id, plan_id=plan_id, idempotency_key="sum-a")
        )
        order_b = await transaction_repository.create(
            _order_dto(user_id=buyer_b.id, plan_id=plan_id, idempotency_key="sum-b")
        )
    await transaction_repository.mark_status(order_a.id, TransactionStatus.PAID)
    await transaction_repository.mark_status(order_b.id, TransactionStatus.PAID)

    totals = await transaction_repository.sum_paid_final_price_by_user_ids([buyer_a.id, buyer_b.id])

    assert totals == {Currency.RUB: Decimal("1000")}


async def test_sum_paid_final_price_by_user_ids_ignores_unpaid_and_unlisted_users(
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
    user_repository: UserRepository,
    plan_id: int,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="c", telegram_id=900_103))
    unpaid_buyer = await user_repository.create(CreateUserDto(name="d", telegram_id=900_104))

    async with uow:
        paid = await transaction_repository.create(
            _order_dto(user_id=buyer.id, plan_id=plan_id, idempotency_key="sum-c")
        )
        await transaction_repository.create(
            _order_dto(user_id=unpaid_buyer.id, plan_id=plan_id, idempotency_key="sum-d")
        )
    await transaction_repository.mark_status(paid.id, TransactionStatus.PAID)

    totals = await transaction_repository.sum_paid_final_price_by_user_ids([buyer.id])

    assert totals == {Currency.RUB: Decimal("500")}


async def test_sum_paid_final_price_by_user_ids_empty_input_returns_empty_dict(
    transaction_repository: TransactionRepository,
) -> None:
    assert await transaction_repository.sum_paid_final_price_by_user_ids([]) == {}


async def test_list_user_ids_with_paid_order(
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
    user_repository: UserRepository,
    plan_id: int,
) -> None:
    payer = await user_repository.create(CreateUserDto(name="e", telegram_id=900_105))
    non_payer = await user_repository.create(CreateUserDto(name="f", telegram_id=900_106))

    async with uow:
        order = await transaction_repository.create(
            _order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="paid-e")
        )
    await transaction_repository.mark_status(order.id, TransactionStatus.PAID)

    paid_ids = await transaction_repository.list_user_ids_with_paid_order([payer.id, non_payer.id])

    assert paid_ids == {payer.id}


async def test_user_id_queries_chunk_and_merge_beyond_the_in_param_cap(
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
    user_repository: UserRepository,
    plan_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.modules.transactions.repository.MAX_SQL_IN_PARAMS", 2)

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
            order = await transaction_repository.create(
                _order_dto(user_id=buyer.id, plan_id=plan_id, idempotency_key=f"chunk-rub-{i}")
            )
            await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
        for i, buyer in enumerate(usd_buyers):
            order = await transaction_repository.create(
                CreateTransactionDto(
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
            await transaction_repository.mark_status(order.id, TransactionStatus.PAID)

    all_ids = [b.id for b in rub_buyers + usd_buyers]

    totals = await transaction_repository.sum_paid_final_price_by_user_ids(all_ids)
    assert totals == {Currency.RUB: Decimal("1500"), Currency.USD: Decimal("200")}

    paid_ids = await transaction_repository.list_user_ids_with_paid_order(all_ids)
    assert paid_ids == set(all_ids)


async def test_count_paid_since_excludes_pending_and_old_orders(
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        old_order = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="count-paid-old")
        )
    await transaction_repository.mark_status(old_order.id, TransactionStatus.PAID)
    # now() is frozen for the test transaction, so both rows get the same
    # updated_at; the old one is backdated by hand
    now = datetime_now()
    await session.execute(
        update(Transaction)
        .where(Transaction.id == old_order.id)
        .values(updated_at=now - timedelta(days=1))
    )
    since = now - timedelta(hours=1)
    async with uow:
        new_paid = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="count-paid-new")
        )
        pending = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="count-paid-pending")
        )
    await transaction_repository.mark_status(new_paid.id, TransactionStatus.PAID)

    count = await transaction_repository.count_paid_since(since)

    assert count == 1
    assert pending.status == TransactionStatus.PENDING


async def test_sum_paid_final_price_since_groups_by_currency(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    # A generous past `since` (not datetime_now() captured mid-test) --
    # see the note on Postgres's frozen-per-transaction now() above.
    since = datetime_now() - timedelta(days=1)
    async with uow:
        rub_order = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="sum-rub")
        )
        usd_order_data = _order_dto(
            user_id=user_id, plan_id=plan_id, idempotency_key="sum-usd"
        ).__dict__
        usd_order = await transaction_repository.create(
            CreateTransactionDto(
                **{
                    **usd_order_data,
                    "currency": Currency.USD,
                    "base_price": Decimal("5"),
                    "final_price": Decimal("5"),
                }
            )
        )
    await transaction_repository.mark_status(rub_order.id, TransactionStatus.PAID)
    await transaction_repository.mark_status(usd_order.id, TransactionStatus.PAID)

    totals = await transaction_repository.sum_paid_final_price_since(since)

    assert totals == {Currency.RUB: Decimal("500"), Currency.USD: Decimal("5")}


async def test_daily_paid_revenue_by_currency_groups_by_day_and_currency(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    since = datetime_now() - timedelta(days=1)
    async with uow:
        order = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="daily-rev")
        )
    await transaction_repository.mark_status(order.id, TransactionStatus.PAID)

    daily = await transaction_repository.daily_paid_revenue_by_currency(since)

    total_revenue = sum(amount for by_currency in daily.values() for amount in by_currency.values())
    assert total_revenue == Decimal("500")


async def test_list_user_ids_with_multiple_paid_orders_requires_more_than_one(
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    single_payer = await user_repository.create(CreateUserDto(name="Single", telegram_id=900_101))

    async with uow:
        first = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="multi-1")
        )
        second = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="multi-2")
        )
        only = await transaction_repository.create(
            _order_dto(user_id=single_payer.id, plan_id=plan_id, idempotency_key="multi-3")
        )
    await transaction_repository.mark_status(first.id, TransactionStatus.PAID)
    await transaction_repository.mark_status(second.id, TransactionStatus.PAID)
    await transaction_repository.mark_status(only.id, TransactionStatus.PAID)

    result = await transaction_repository.list_user_ids_with_multiple_paid_orders(
        [user_id, single_payer.id]
    )

    assert result == {user_id}


async def test_list_paid_user_month_pairs_dedupes_within_a_month_and_respects_since(
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        early_this_month = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="pairs-1")
        )
        later_this_month = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="pairs-2")
        )
        too_old = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="pairs-3")
        )
    await transaction_repository.mark_status(early_this_month.id, TransactionStatus.PAID)
    await transaction_repository.mark_status(later_this_month.id, TransactionStatus.PAID)
    await transaction_repository.mark_status(too_old.id, TransactionStatus.PAID)
    await session.execute(
        update(Transaction)
        .where(Transaction.id == too_old.id)
        .values(updated_at=datetime_now() - timedelta(days=400))
    )

    pairs = await transaction_repository.list_paid_user_month_pairs(
        [user_id], datetime_now() - timedelta(days=60)
    )

    assert len(pairs) == 1
    result_user_id, month = pairs[0]
    assert result_user_id == user_id
    assert month == datetime_now().date().replace(day=1)


async def test_lookups_are_scoped_to_the_gateway(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> None:
    async with uow:
        created = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="key-scope")
        )
        await transaction_repository.mark_status(
            created.id, TransactionStatus.PENDING, external_payment_id="shared-id"
        )

    by_key = await transaction_repository.get_by_idempotency_key(
        "key-scope", gateway_type=created.gateway_type
    )
    assert by_key is not None and by_key.id == created.id
    assert (
        await transaction_repository.get_by_idempotency_key(
            "key-scope", gateway_type=PaymentGatewayType.YOOMONEY
        )
        is None
    )

    by_external = await transaction_repository.get_by_external_payment_id(
        "shared-id", gateway_type=created.gateway_type
    )
    assert by_external is not None and by_external.id == created.id
    assert (
        await transaction_repository.get_by_external_payment_id(
            "shared-id", gateway_type=PaymentGatewayType.YOOMONEY
        )
        is None
    )
