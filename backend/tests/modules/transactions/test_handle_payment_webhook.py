import asyncio
from datetime import timedelta
from decimal import Decimal
from typing import Optional

import pytest
from sqlalchemy import update

from app.core.db.models.transaction import Transaction
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PromocodeRewardType,
    PurchaseType,
    TransactionStatus,
)
from app.core.exceptions import PaymentGatewayError
from app.core.utils.time import datetime_now
from app.modules.gateways.repository import GatewayRepository
from app.modules.promocodes.dto import CreatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.transactions.dto import CreateTransactionDto, HandleWebhookDto, WebhookRequest
from app.modules.transactions.gateways.base import ProviderPayment, WebhookAck, WebhookSignal
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.usecases import (
    HandlePaymentWebhookUseCase,
    PruneExpiredTransactionsUseCase,
)
from app.modules.users.dto import UpdateUserDto
from tests.fakes.dispatch import RecordingDispatch
from tests.fakes.events import RecordingEventPublisher
from tests.modules.subscriptions.factories import make_plan_snapshot

_PAID = ProviderPayment(
    paid=True, amount=Decimal("500"), reference="gated-ref", provider_payment_id="yk-gated"
)


@pytest.fixture
def purchase_dispatch() -> RecordingDispatch:
    return RecordingDispatch()


class _GatedGateway:
    trusted_networks: tuple[str, ...] = ()

    def __init__(self, gate: asyncio.Event, entered: asyncio.Event) -> None:
        self._gate = gate
        self._entered = entered

    async def parse_webhook(self, request: object) -> Optional[WebhookSignal]:
        return WebhookSignal(reference="gated-ref", claims_paid=True)

    async def confirm(self, order: object, signal: object) -> Optional[ProviderPayment]:
        self._entered.set()
        await self._gate.wait()
        return _PAID

    def webhook_ack(self, signal: object) -> WebhookAck:
        return WebhookAck()


class _GatedFactory(PaymentGatewayFactory):
    def __init__(self, gateway: _GatedGateway) -> None:
        self._gateway = gateway

    def build(self, gateway_type, settings):  # type: ignore[no-untyped-def]
        return self._gateway  # type: ignore[return-value]


def _pending_order(
    *, user_id: int, plan_id: int, source: DiscountSource, promocode_id: Optional[int] = None
) -> CreateTransactionDto:
    percent = 20 if source is DiscountSource.PURCHASE else 0
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
        discount_percent=percent,
        discount_source=source,
        discount_promocode_id=promocode_id,
        final_price=Decimal("500"),
        anchor_base_price=Decimal("500"),
        anchor_final_price=Decimal("500"),
        customer_email=None,
        idempotency_key="gated-ref",
        expires_at=datetime_now() + timedelta(minutes=30),
    )


async def _paid_while_order_expires(
    *,
    source: DiscountSource,
    transaction_repository,
    user_repository,
    uow,
    user_id,
    plan_id,
    gateway_repository: GatewayRepository,
    promocode_repository: PromocodeRepository,
    purchase_dispatch: RecordingDispatch,
):  # type: ignore[no-untyped-def]
    promocode_id = None
    async with uow:
        await user_repository.update_fields(user_id, UpdateUserDto(purchase_discount=0))
        if source is DiscountSource.PURCHASE:
            promocode = await promocode_repository.create(
                CreatePromocodeDto(
                    code="GATED20", reward_type=PromocodeRewardType.PURCHASE_DISCOUNT, reward=20
                )
            )
            promocode_id = promocode.id
        order = await transaction_repository.create(
            _pending_order(
                user_id=user_id, plan_id=plan_id, source=source, promocode_id=promocode_id
            )
        )
    gate, entered = asyncio.Event(), asyncio.Event()
    use_case = HandlePaymentWebhookUseCase(
        transaction_repository,
        gateway_repository,
        _GatedFactory(_GatedGateway(gate, entered)),
        user_repository,
        None,  # type: ignore[arg-type]
        uow,
        purchase_dispatch,
    )
    dto = HandleWebhookDto(
        gateway_type=PaymentGatewayType.YOOKASSA,
        request=WebhookRequest(body=b"{}", headers={}),
    )
    task = asyncio.create_task(use_case.system(dto))
    await entered.wait()
    async with uow:
        await transaction_repository.session.execute(
            update(Transaction)
            .where(Transaction.id == order.id)
            .values(expires_at=datetime_now() - timedelta(minutes=1))
        )
    await PruneExpiredTransactionsUseCase(
        transaction_repository, user_repository, uow, RecordingEventPublisher()
    ).system()
    gate.set()
    await task
    return order


async def test_paid_does_not_overwrite_cancel_with_restored_discount(
    transaction_repository,
    user_repository,
    uow,
    user_id,
    plan_id,
    gateway_repository,
    promocode_repository,
    purchase_dispatch,
) -> None:
    order = await _paid_while_order_expires(
        source=DiscountSource.PURCHASE,
        transaction_repository=transaction_repository,
        user_repository=user_repository,
        uow=uow,
        user_id=user_id,
        plan_id=plan_id,
        gateway_repository=gateway_repository,
        promocode_repository=promocode_repository,
        purchase_dispatch=purchase_dispatch,
    )

    assert (await transaction_repository.get_by_id(order.id)).status is TransactionStatus.CANCELED
    assert purchase_dispatch.messages == []
    assert (await user_repository.find_by_id(user_id)).purchase_discount == order.discount_percent


async def test_paid_after_plain_cancel_is_still_fulfilled(
    transaction_repository,
    user_repository,
    uow,
    user_id,
    plan_id,
    gateway_repository,
    promocode_repository,
    purchase_dispatch,
) -> None:
    order = await _paid_while_order_expires(
        source=DiscountSource.NONE,
        transaction_repository=transaction_repository,
        user_repository=user_repository,
        uow=uow,
        user_id=user_id,
        plan_id=plan_id,
        gateway_repository=gateway_repository,
        promocode_repository=promocode_repository,
        purchase_dispatch=purchase_dispatch,
    )

    fetched = await transaction_repository.get_by_id(order.id)
    assert fetched.status is TransactionStatus.PAID
    assert fetched.external_payment_id == "yk-gated"
    assert len(purchase_dispatch.messages) == 1


async def test_paid_that_keeps_losing_the_status_race_raises_for_redelivery(
    transaction_repository,
    user_repository,
    uow,
    user_id,
    plan_id,
    gateway_repository,
    purchase_dispatch,
    monkeypatch,
) -> None:
    async with uow:
        await transaction_repository.create(
            _pending_order(user_id=user_id, plan_id=plan_id, source=DiscountSource.NONE)
        )
    gate, entered = asyncio.Event(), asyncio.Event()
    gate.set()

    async def _always_lost(*args, **kwargs) -> bool:  # type: ignore[no-untyped-def]
        return False

    monkeypatch.setattr(transaction_repository, "mark_status_if", _always_lost)
    use_case = HandlePaymentWebhookUseCase(
        transaction_repository,
        gateway_repository,
        _GatedFactory(_GatedGateway(gate, entered)),
        user_repository,
        None,  # type: ignore[arg-type]
        uow,
        purchase_dispatch,
    )
    dto = HandleWebhookDto(
        gateway_type=PaymentGatewayType.YOOKASSA,
        request=WebhookRequest(body=b"{}", headers={}),
    )

    with pytest.raises(PaymentGatewayError):
        await use_case.system(dto)

    assert purchase_dispatch.messages == []
