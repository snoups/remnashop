from datetime import timedelta
from decimal import Decimal

import pytest

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
from app.modules.payments.usecases.list_payment_orders import (
    ListPaymentOrdersInput,
    ListPaymentOrdersUseCase,
)
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
) -> ListPaymentOrdersUseCase:
    return ListPaymentOrdersUseCase(payment_order_repository)


@pytest.fixture
def get_payment_order_use_case(
    payment_order_repository: PaymentOrderRepository,
) -> GetPaymentOrderUseCase:
    return GetPaymentOrderUseCase(payment_order_repository)


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

    orders, total = await list_payment_orders_use_case(
        admin_actor, ListPaymentOrdersInput(status=PaymentOrderStatus.PAID)
    )
    assert total == 1
    assert [order.id for order in orders] == [paid.id]

    orders, total = await list_payment_orders_use_case(admin_actor, ListPaymentOrdersInput())
    ids = {order.id for order in orders}
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
    assert fetched.id == created.id


async def test_get_payment_order_raises_not_found_for_a_missing_id(
    get_payment_order_use_case: GetPaymentOrderUseCase, admin_actor: UserDto
) -> None:
    with pytest.raises(NotFoundError):
        await get_payment_order_use_case(admin_actor, 999_999_999)
