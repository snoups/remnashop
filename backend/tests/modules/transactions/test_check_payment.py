from datetime import timedelta
from decimal import Decimal
from typing import Optional

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    Role,
    TransactionStatus,
)
from app.core.exceptions import ConflictError
from app.core.utils.time import datetime_now
from app.modules.gateways.repository import GatewayRepository
from app.modules.transactions.dto import (
    CheckTransactionPaymentDto,
    CreateTransactionDto,
    TransactionDto,
)
from app.modules.transactions.events import TransactionPaymentConfirmedEvent
from app.modules.transactions.gateways.base import ProviderPayment
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases import CheckTransactionPaymentUseCase
from app.modules.users import UserRepository
from app.modules.users.dto import CreateUserDto, UserDto
from tests.fakes.dispatch import RecordingDispatch
from tests.fakes.events import RecordingEventPublisher
from tests.modules.subscriptions.factories import make_plan_snapshot


class _StubGateway:
    def __init__(self, payment: Optional[ProviderPayment], *, supported: bool = True) -> None:
        self.supports_status_check = supported
        self._payment = payment

    async def check_payment(self, order: TransactionDto) -> Optional[ProviderPayment]:
        return self._payment


class _StubFactory(PaymentGatewayFactory):
    def __init__(self, gateway: _StubGateway) -> None:
        self._gateway = gateway

    def build(self, gateway_type, settings):  # type: ignore[no-untyped-def]
        return self._gateway  # type: ignore[return-value]


_PAID = ProviderPayment(
    paid=True, amount=Decimal("500"), reference="check-ref", provider_payment_id="yk-found"
)


@pytest.fixture
async def admin_actor(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(
        CreateUserDto(name="check-admin", role=Role.ADMIN, telegram_id=800_101)
    )


async def _order(
    repository: TransactionRepository, uow: UnitOfWork, *, user_id: int, plan_id: int
) -> TransactionDto:
    async with uow:
        return await repository.create(
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
                idempotency_key="check-ref",
                expires_at=datetime_now() + timedelta(minutes=30),
            )
        )


def _use_case(
    gateway: _StubGateway,
    session: AsyncSession,
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    events: RecordingEventPublisher,
    dispatch: RecordingDispatch,
) -> CheckTransactionPaymentUseCase:
    return CheckTransactionPaymentUseCase(
        transaction_repository,
        GatewayRepository(session),
        _StubFactory(gateway),
        user_repository,
        events,
        uow,
        dispatch,
    )


async def test_a_payment_the_gateway_confirms_settles_the_order(
    session: AsyncSession,
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    admin_actor: UserDto,
    user_id: int,
    plan_id: int,
) -> None:
    order = await _order(transaction_repository, uow, user_id=user_id, plan_id=plan_id)
    events, dispatch = RecordingEventPublisher(), RecordingDispatch()
    use_case = _use_case(
        _StubGateway(_PAID), session, transaction_repository, user_repository, uow, events, dispatch
    )

    result = await use_case(
        admin_actor, CheckTransactionPaymentDto(transaction_id=order.id, client_ip="10.0.0.1")
    )

    assert result.paid
    assert result.transaction.order.status is TransactionStatus.PAID
    assert result.transaction.order.external_payment_id == "yk-found"
    (event,) = events.events
    assert isinstance(event, TransactionPaymentConfirmedEvent)
    assert event.previous_status is TransactionStatus.PENDING
    assert [message["idempotency_key"] for message in dispatch.messages] == ["check-ref"]

    with pytest.raises(ConflictError):
        await use_case(
            admin_actor, CheckTransactionPaymentDto(transaction_id=order.id, client_ip="10.0.0.1")
        )


async def test_an_unconfirmed_payment_leaves_the_order_as_it_was(
    session: AsyncSession,
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    admin_actor: UserDto,
    user_id: int,
    plan_id: int,
) -> None:
    order = await _order(transaction_repository, uow, user_id=user_id, plan_id=plan_id)
    async with uow:
        await transaction_repository.mark_status(order.id, TransactionStatus.CANCELED)
    events, dispatch = RecordingEventPublisher(), RecordingDispatch()
    use_case = _use_case(
        _StubGateway(None), session, transaction_repository, user_repository, uow, events, dispatch
    )

    result = await use_case(
        admin_actor, CheckTransactionPaymentDto(transaction_id=order.id, client_ip="10.0.0.1")
    )

    assert not result.paid
    assert result.transaction.order.status is TransactionStatus.CANCELED
    assert events.events == []
    assert dispatch.messages == []


async def test_a_gateway_without_a_status_lookup_is_refused(
    session: AsyncSession,
    transaction_repository: TransactionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    admin_actor: UserDto,
    user_id: int,
    plan_id: int,
) -> None:
    order = await _order(transaction_repository, uow, user_id=user_id, plan_id=plan_id)
    use_case = _use_case(
        _StubGateway(_PAID, supported=False),
        session,
        transaction_repository,
        user_repository,
        uow,
        RecordingEventPublisher(),
        RecordingDispatch(),
    )

    with pytest.raises(ConflictError):
        await use_case(
            admin_actor, CheckTransactionPaymentDto(transaction_id=order.id, client_ip="10.0.0.1")
        )
