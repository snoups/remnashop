from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PaymentOrderStatus,
    PurchaseType,
    Role,
)
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.utils.time import datetime_now
from app.modules.payments.dto import CreatePaymentOrderDto
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.payments.usecases.get_payment_order import GetPaymentOrderUseCase
from app.modules.payments.usecases.get_payment_order_summary import (
    GetPaymentOrderSummaryInput,
    GetPaymentOrderSummaryUseCase,
)
from app.modules.payments.usecases.list_payment_orders import (
    ListPaymentOrdersInput,
    ListPaymentOrdersUseCase,
)
from app.modules.pricing import PricingRepository
from app.modules.users import UserRepository
from app.modules.users.dto import CreateUserDto, UserDto
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


@pytest.fixture
async def admin_actor(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(
        CreateUserDto(name="payments-admin", role=Role.ADMIN, telegram_id=800_001)
    )


@pytest.fixture
def list_payment_orders_use_case(
    payment_order_repository: PaymentOrderRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> ListPaymentOrdersUseCase:
    return ListPaymentOrdersUseCase(payment_order_repository, user_repository, uow)


@pytest.fixture
def get_payment_order_use_case(
    payment_order_repository: PaymentOrderRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> GetPaymentOrderUseCase:
    return GetPaymentOrderUseCase(payment_order_repository, user_repository, uow)


async def test_list_payment_orders_requires_the_payments_view_permission(
    list_payment_orders_use_case: ListPaymentOrdersUseCase, user_id: int, plan_id: int
) -> None:
    regular_actor = UserDto(id=user_id, name="not-an-admin", role=Role.USER)
    with pytest.raises(PermissionDeniedError):
        await list_payment_orders_use_case(regular_actor, ListPaymentOrdersInput())


async def test_list_payment_orders_filters_by_status(
    list_payment_orders_use_case: ListPaymentOrdersUseCase,
    payment_order_repository: PaymentOrderRepository,
    admin_actor: UserDto,
    uow,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        pending = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="list-pending")
        )
        paid = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="list-paid")
        )
        await payment_order_repository.mark_status(paid.id, PaymentOrderStatus.PAID)

    items, total = await list_payment_orders_use_case(
        admin_actor, ListPaymentOrdersInput(status=PaymentOrderStatus.PAID)
    )
    assert total == 1
    assert [item.order.id for item in items] == [paid.id]
    assert items[0].user is not None and items[0].user.name == "buyer"

    items, total = await list_payment_orders_use_case(admin_actor, ListPaymentOrdersInput())
    ids = {item.order.id for item in items}
    assert {pending.id, paid.id} <= ids


async def test_get_payment_order_requires_the_payments_view_permission(
    get_payment_order_use_case: GetPaymentOrderUseCase, user_id: int
) -> None:
    regular_actor = UserDto(id=user_id, name="not-an-admin", role=Role.USER)
    with pytest.raises(PermissionDeniedError):
        await get_payment_order_use_case(regular_actor, 1)


async def test_get_payment_order_returns_the_order(
    get_payment_order_use_case: GetPaymentOrderUseCase,
    payment_order_repository: PaymentOrderRepository,
    admin_actor: UserDto,
    uow,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        created = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="get-one")
        )

    fetched = await get_payment_order_use_case(admin_actor, created.id)
    assert fetched.order.id == created.id
    assert fetched.user is not None and fetched.user.telegram_id == 900_001


async def test_get_payment_order_raises_not_found_for_a_missing_id(
    get_payment_order_use_case: GetPaymentOrderUseCase, admin_actor: UserDto
) -> None:
    with pytest.raises(NotFoundError):
        await get_payment_order_use_case(admin_actor, 999_999_999)


async def test_get_payment_order_summary_counts_and_converts_paid_revenue(
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
    admin_actor: UserDto,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="summary-pending")
        )
        paid = await payment_order_repository.create(
            replace(
                _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="summary-paid"),
                base_price=Decimal("625"),
                discount_percent=20,
            )
        )
        await payment_order_repository.mark_status(paid.id, PaymentOrderStatus.PAID)
        rates = await pricing_repository.get_rate_table()

    use_case = GetPaymentOrderSummaryUseCase(payment_order_repository, pricing_repository, uow)
    summary = await use_case(admin_actor, GetPaymentOrderSummaryInput())

    expected_revenue = (
        Decimal("500")
        / rates.for_currency(Currency.RUB).rate
        * rates.for_currency(rates.anchor).rate
    )
    assert summary.report_currency == rates.anchor
    assert (summary.total_count, summary.pending_count, summary.paid_count) == (2, 1, 1)
    assert summary.conversion_rate == Decimal("0.5")
    assert summary.revenue == expected_revenue
    assert summary.average_check == expected_revenue
    assert summary.average_discount == Decimal("0.2")
    expected_base = (
        Decimal("625")
        / rates.for_currency(Currency.RUB).rate
        * rates.for_currency(rates.anchor).rate
    )
    assert summary.discount_amount == expected_base - expected_revenue
