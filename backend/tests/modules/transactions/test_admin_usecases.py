from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseType,
    Role,
    RoundingMode,
    TransactionStatus,
)
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.pricing import PricingRepository
from app.modules.pricing.dto import UpdateCurrencyRateDto
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.transactions.dto import (
    CreateTransactionDto,
    GetTransactionSummaryDto,
    ListTransactionsDto,
)
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases.fulfill_transaction import FulfillTransactionUseCase
from app.modules.transactions.usecases.get_transaction import GetTransactionUseCase
from app.modules.transactions.usecases.get_transaction_summary import GetTransactionSummaryUseCase
from app.modules.transactions.usecases.list_transactions import ListTransactionsUseCase
from app.modules.users import UserRepository
from app.modules.users.dto import CreateUserDto, UserDto
from tests.fakes.dispatch import RecordingDispatch
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
        anchor_base_price=Decimal("500"),
        anchor_final_price=Decimal("500"),
        customer_email=None,
        idempotency_key=idempotency_key,
        expires_at=datetime_now() + timedelta(minutes=30),
    )


@pytest.fixture
async def admin_actor(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(
        CreateUserDto(name="transactions-admin", role=Role.ADMIN, telegram_id=800_001)
    )


@pytest.fixture
def list_transactions_use_case(
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> ListTransactionsUseCase:
    return ListTransactionsUseCase(transaction_repository, user_repository, uow)


@pytest.fixture
def get_transaction_use_case(
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> GetTransactionUseCase:
    return GetTransactionUseCase(transaction_repository, user_repository, uow)


async def test_list_transactions_requires_the_transactions_view_permission(
    list_transactions_use_case: ListTransactionsUseCase, user_id: int, plan_id: int
) -> None:
    regular_actor = UserDto(id=user_id, name="not-an-admin", role=Role.USER)
    with pytest.raises(PermissionDeniedError):
        await list_transactions_use_case(regular_actor, ListTransactionsDto())


async def test_list_transactions_filters_by_status(
    list_transactions_use_case: ListTransactionsUseCase,
    transaction_repository: TransactionRepository,
    admin_actor: UserDto,
    uow,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        pending = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="list-pending")
        )
        paid = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="list-paid")
        )
        await transaction_repository.mark_status(paid.id, TransactionStatus.PAID)

    items, total = await list_transactions_use_case(
        admin_actor, ListTransactionsDto(status=TransactionStatus.PAID)
    )
    assert total == 1
    assert [item.order.id for item in items] == [paid.id]
    assert items[0].user is not None and items[0].user.name == "buyer"

    items, total = await list_transactions_use_case(admin_actor, ListTransactionsDto())
    ids = {item.order.id for item in items}
    assert {pending.id, paid.id} <= ids


async def test_get_transaction_requires_the_transactions_view_permission(
    get_transaction_use_case: GetTransactionUseCase, user_id: int
) -> None:
    regular_actor = UserDto(id=user_id, name="not-an-admin", role=Role.USER)
    with pytest.raises(PermissionDeniedError):
        await get_transaction_use_case(regular_actor, 1)


async def test_get_transaction_returns_the_order(
    get_transaction_use_case: GetTransactionUseCase,
    transaction_repository: TransactionRepository,
    admin_actor: UserDto,
    uow,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        created = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="get-one")
        )

    fetched = await get_transaction_use_case(admin_actor, created.id)
    assert fetched.order.id == created.id
    assert fetched.user is not None and fetched.user.telegram_id == 900_001


async def test_get_transaction_hides_a_staff_buyer_from_an_admin(
    get_transaction_use_case: GetTransactionUseCase,
    list_transactions_use_case: ListTransactionsUseCase,
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    admin_actor: UserDto,
    uow,
    plan_id: int,
) -> None:
    staff = await user_repository.create(
        CreateUserDto(name="staff", role=Role.ADMIN, telegram_id=800_002)
    )
    async with uow:
        created = await transaction_repository.create(
            replace(
                _order_dto(user_id=staff.id, plan_id=plan_id, idempotency_key="staff-order"),
                customer_email="staff@example.com",
            )
        )
    owner_actor = UserDto(id=1, name="owner", role=Role.OWNER)

    hidden = await get_transaction_use_case(admin_actor, created.id)
    assert hidden.user is None and hidden.order.customer_email is None

    shown = await get_transaction_use_case(owner_actor, created.id)
    assert shown.user is not None and shown.order.customer_email == "staff@example.com"

    items, _ = await list_transactions_use_case(admin_actor, ListTransactionsDto(user_id=staff.id))
    assert items and all(i.user is None and i.order.customer_email is None for i in items)


async def test_search_does_not_match_a_hidden_staff_email(
    list_transactions_use_case: ListTransactionsUseCase,
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    admin_actor: UserDto,
    uow,
    plan_id: int,
) -> None:
    staff = await user_repository.create(
        CreateUserDto(name="staff", role=Role.ADMIN, telegram_id=800_003)
    )
    async with uow:
        await transaction_repository.create(
            replace(
                _order_dto(user_id=staff.id, plan_id=plan_id, idempotency_key="staff-search"),
                customer_email="probe-me@example.com",
            )
        )
    owner_actor = UserDto(id=1, name="owner", role=Role.OWNER)
    data = ListTransactionsDto(search="probe-me")

    items, _ = await list_transactions_use_case(admin_actor, data)
    assert items == []

    items, _ = await list_transactions_use_case(owner_actor, data)
    assert len(items) == 1


async def test_get_transaction_raises_not_found_for_a_missing_id(
    get_transaction_use_case: GetTransactionUseCase, admin_actor: UserDto
) -> None:
    with pytest.raises(NotFoundError):
        await get_transaction_use_case(admin_actor, 999_999_999)


async def test_get_transaction_summary_counts_and_converts_paid_revenue(
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    admin_actor: UserDto,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="summary-pending")
        )
        paid = await transaction_repository.create(
            replace(
                _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="summary-paid"),
                base_price=Decimal("625"),
                anchor_base_price=Decimal("625"),
                discount_percent=20,
            )
        )
        await transaction_repository.mark_status(paid.id, TransactionStatus.PAID)
        rates = await pricing_repository.get_rate_table()

    use_case = GetTransactionSummaryUseCase(transaction_repository, pricing_repository, uow)
    summary = await use_case(admin_actor, GetTransactionSummaryDto())

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


async def test_summary_does_not_float_after_rate_change(
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    admin_actor: UserDto,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        await pricing_repository.get_rate_table()
        order = await transaction_repository.create(
            replace(
                _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="float-paid"),
                base_price=Decimal("900"),
                final_price=Decimal("900"),
                anchor_base_price=Decimal("10"),
                anchor_final_price=Decimal("10"),
            )
        )
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
        await pricing_repository.update_rate(
            UpdateCurrencyRateDto(
                currency=Currency.RUB,
                rate=Decimal("120"),
                rounding_mode=RoundingMode.INTEGER,
                charm_ending=None,
                min_amount=Decimal("10"),
            )
        )

    summary = await GetTransactionSummaryUseCase(transaction_repository, pricing_repository, uow)(
        admin_actor, GetTransactionSummaryDto()
    )

    assert summary.revenue == Decimal("10")


async def test_fulfill_transaction_marks_a_failed_order_paid_and_dispatches_it(
    transaction_repository: TransactionRepository,
    idempotency_repository: PurchaseIdempotencyRepository,
    user_repository: UserRepository,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
    admin_actor: UserDto,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        failed = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="fulfill-failed")
        )
        await transaction_repository.mark_status(failed.id, TransactionStatus.FAILED)
        pending = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="fulfill-pending")
        )
    dispatch = RecordingDispatch()
    use_case = FulfillTransactionUseCase(
        transaction_repository,
        idempotency_repository,
        user_repository,
        event_publisher,
        uow,
        dispatch,
    )

    result = await use_case(admin_actor, failed.id)

    assert result.order.status is TransactionStatus.PAID
    assert [message["idempotency_key"] for message in dispatch.messages] == ["fulfill-failed"]

    with pytest.raises(ConflictError):
        await use_case(admin_actor, pending.id)
    assert len(dispatch.messages) == 1
