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
    TransactionStatus,
)
from app.core.utils.time import datetime_now
from app.modules.gateways.repository import GatewayRepository
from app.modules.transactions.dto import (
    CreateTransactionDto,
    StarsPaymentDto,
    StarsPreCheckoutDto,
    TransactionDto,
)
from app.modules.transactions.gateways.telegram_stars import stars_amount
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases import (
    ConfirmStarsPaymentUseCase,
    ValidateStarsPreCheckoutUseCase,
)
from app.modules.users import UserRepository
from app.modules.users.dto import CreateUserDto, UserDto
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.subscriptions.factories import make_plan_snapshot


def _stars_order(
    *, user_id: int, plan_id: int, source: DiscountSource = DiscountSource.NONE
) -> CreateTransactionDto:
    return CreateTransactionDto(
        user_id=user_id,
        plan_id=plan_id,
        plan_snapshot=make_plan_snapshot(plan_id=plan_id),
        duration_days=30,
        currency=Currency.XTR,
        purchase_type=PurchaseType.NEW,
        target_subscription_id=None,
        gateway_type=PaymentGatewayType.TELEGRAM_STARS,
        base_price=Decimal("50"),
        discount_percent=20 if source is DiscountSource.PURCHASE else 0,
        discount_source=source,
        final_price=Decimal("50"),
        anchor_base_price=Decimal("50"),
        anchor_final_price=Decimal("50"),
        customer_email=None,
        idempotency_key="stars-ref",
        expires_at=datetime_now() + timedelta(minutes=30),
    )


@pytest.fixture
def purchase_dispatch() -> RecordingDispatch:
    return RecordingDispatch()


@pytest.fixture
def validate(
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    gateway_repository: GatewayRepository,
    uow: UnitOfWork,
) -> ValidateStarsPreCheckoutUseCase:
    return ValidateStarsPreCheckoutUseCase(
        transaction_repository, user_repository, gateway_repository, uow
    )


@pytest.fixture
def confirm(
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    purchase_dispatch: RecordingDispatch,
) -> ConfirmStarsPaymentUseCase:
    return ConfirmStarsPaymentUseCase(
        transaction_repository, user_repository, uow, purchase_dispatch
    )


@pytest.fixture
async def buyer(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(CreateUserDto(name="stars-buyer", telegram_id=800_001))


async def _create(
    transaction_repository: TransactionRepository, uow: UnitOfWork, dto: CreateTransactionDto
) -> TransactionDto:
    async with uow:
        created = await transaction_repository.create(dto)
        return await transaction_repository.mark_status(created.id, TransactionStatus.PENDING)


@pytest.fixture
async def pending_stars_order(
    transaction_repository: TransactionRepository, uow: UnitOfWork, buyer: UserDto, plan_id: int
) -> TransactionDto:
    return await _create(
        transaction_repository, uow, _stars_order(user_id=buyer.id, plan_id=plan_id)
    )


@pytest.fixture
async def stars_paid_only(gateway_repository: GatewayRepository, uow: UnitOfWork) -> None:
    async with uow:
        await gateway_repository.update_settings(
            PaymentGatewayType.TELEGRAM_STARS, {"require_paid_purchase": "true"}
        )


def _pre(buyer: UserDto, order: TransactionDto) -> StarsPreCheckoutDto:
    assert buyer.telegram_id is not None
    return StarsPreCheckoutDto(
        telegram_id=buyer.telegram_id,
        payload=order.idempotency_key,
        currency="XTR",
        total_amount=stars_amount(order),
    )


def _paid(buyer: UserDto, order: TransactionDto, *, charge_id: str) -> StarsPaymentDto:
    assert buyer.telegram_id is not None
    return StarsPaymentDto(
        telegram_id=buyer.telegram_id,
        payload=order.idempotency_key,
        currency="XTR",
        total_amount=stars_amount(order),
        charge_id=charge_id,
    )


async def test_pre_checkout_accepts_a_matching_pending_order(
    validate: ValidateStarsPreCheckoutUseCase, pending_stars_order: TransactionDto, buyer: UserDto
) -> None:
    assert await validate.system(_pre(buyer, pending_stars_order)) is True


@pytest.mark.parametrize(
    "change",
    [
        {"telegram_id": 1},
        {"total_amount": 1},
        {"currency": "USD"},
        {"payload": "unknown"},
    ],
)
async def test_pre_checkout_rejects_a_mismatch(
    validate: ValidateStarsPreCheckoutUseCase,
    pending_stars_order: TransactionDto,
    buyer: UserDto,
    change: dict[str, object],
) -> None:
    assert await validate.system(replace(_pre(buyer, pending_stars_order), **change)) is False


async def test_pre_checkout_rejects_a_canceled_order(
    validate: ValidateStarsPreCheckoutUseCase,
    pending_stars_order: TransactionDto,
    buyer: UserDto,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await transaction_repository.mark_status(pending_stars_order.id, TransactionStatus.CANCELED)
    assert await validate.system(_pre(buyer, pending_stars_order)) is False


async def test_pre_checkout_rejects_a_blocked_buyer(
    validate: ValidateStarsPreCheckoutUseCase,
    pending_stars_order: TransactionDto,
    buyer: UserDto,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await user_repository.set_blocked(buyer.id, True)
    assert await validate.system(_pre(buyer, pending_stars_order)) is False


async def test_pre_checkout_rejects_without_a_paid_purchase_when_required(
    validate: ValidateStarsPreCheckoutUseCase,
    pending_stars_order: TransactionDto,
    buyer: UserDto,
    stars_paid_only: None,
) -> None:
    assert await validate.system(_pre(buyer, pending_stars_order)) is False


async def test_successful_payment_fulfills_once(
    confirm: ConfirmStarsPaymentUseCase,
    pending_stars_order: TransactionDto,
    buyer: UserDto,
    purchase_dispatch: RecordingDispatch,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> None:
    dto = _paid(buyer, pending_stars_order, charge_id="charge-1")
    await confirm.system(dto)
    await confirm.system(dto)

    assert len(purchase_dispatch.messages) == 1
    assert purchase_dispatch.messages[0]["idempotency_key"] == "stars-ref"
    async with uow:
        order = await transaction_repository.get_by_id(pending_stars_order.id)
    assert order.status is TransactionStatus.PAID
    assert order.external_payment_id == "charge-1"


@pytest.mark.parametrize("change", [{"telegram_id": 1}, {"total_amount": 1}, {"currency": "USD"}])
async def test_mismatched_payment_is_not_fulfilled(
    confirm: ConfirmStarsPaymentUseCase,
    pending_stars_order: TransactionDto,
    buyer: UserDto,
    purchase_dispatch: RecordingDispatch,
    transaction_repository: TransactionRepository,
    change: dict[str, object],
) -> None:
    await confirm.system(replace(_paid(buyer, pending_stars_order, charge_id="c"), **change))

    assert purchase_dispatch.messages == []
    order = await transaction_repository.get_by_id(pending_stars_order.id)
    assert order.status is TransactionStatus.PENDING


async def test_late_payment_on_a_canceled_order_is_fulfilled(
    confirm: ConfirmStarsPaymentUseCase,
    pending_stars_order: TransactionDto,
    buyer: UserDto,
    purchase_dispatch: RecordingDispatch,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await transaction_repository.mark_status(pending_stars_order.id, TransactionStatus.CANCELED)

    await confirm.system(_paid(buyer, pending_stars_order, charge_id="late"))

    assert len(purchase_dispatch.messages) == 1


async def test_late_payment_on_a_canceled_discounted_order_is_not_fulfilled(
    confirm: ConfirmStarsPaymentUseCase,
    buyer: UserDto,
    plan_id: int,
    purchase_dispatch: RecordingDispatch,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> None:
    order = await _create(
        transaction_repository,
        uow,
        _stars_order(user_id=buyer.id, plan_id=plan_id, source=DiscountSource.PURCHASE),
    )
    async with uow:
        await transaction_repository.mark_status(order.id, TransactionStatus.CANCELED)

    await confirm.system(_paid(buyer, order, charge_id="late"))

    assert purchase_dispatch.messages == []
    assert (await transaction_repository.get_by_id(order.id)).status is TransactionStatus.CANCELED


async def test_test_order_is_marked_paid_without_fulfillment(
    confirm: ConfirmStarsPaymentUseCase,
    buyer: UserDto,
    plan_id: int,
    purchase_dispatch: RecordingDispatch,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> None:
    order = await _create(
        transaction_repository,
        uow,
        replace(_stars_order(user_id=buyer.id, plan_id=plan_id), is_test=True),
    )

    await confirm.system(_paid(buyer, order, charge_id="test"))

    assert purchase_dispatch.messages == []
    assert (await transaction_repository.get_by_id(order.id)).status is TransactionStatus.PAID
