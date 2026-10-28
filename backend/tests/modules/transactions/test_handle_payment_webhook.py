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
    PurchaseChannel,
    PurchaseType,
    TransactionStatus,
)
from app.core.exceptions import PaymentGatewayError, PermissionDeniedError
from app.core.utils.time import datetime_now
from app.modules.gateways.repository import GatewayRepository
from app.modules.promocodes.dto import CreatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.transactions.dto import CreateTransactionDto, HandleWebhookDto, WebhookRequest
from app.modules.transactions.events import (
    TransactionCanceledEvent,
    TransactionPartiallyRefundedEvent,
    TransactionRefundedEvent,
)
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


class _ReportingGateway:
    def __init__(
        self,
        signal: Optional[WebhookSignal],
        *,
        confirmed: Optional[WebhookSignal] = None,
        disagrees: bool = False,
        trusted_networks: tuple[str, ...] = (),
        parse_error: Optional[Exception] = None,
    ) -> None:
        self._signal = signal
        self._confirmed = confirmed
        self._disagrees = disagrees
        self.trusted_networks = trusted_networks
        self._parse_error = parse_error

    async def parse_webhook(self, request: object) -> Optional[WebhookSignal]:
        if self._parse_error is not None:
            raise self._parse_error
        return self._signal

    async def confirm_reported(
        self, order: object, signal: WebhookSignal
    ) -> Optional[WebhookSignal]:
        if self._disagrees:
            return None
        return self._confirmed or signal

    def is_trusted_source(self, client_ip: str) -> bool:
        return client_ip == "10.0.0.1"

    def webhook_ack(self, signal: object) -> WebhookAck:
        return WebhookAck()


class _FixedFactory(PaymentGatewayFactory):
    def __init__(self, gateway: _ReportingGateway) -> None:
        self._gateway = gateway

    def build(self, gateway_type, settings):  # type: ignore[no-untyped-def]
        return self._gateway  # type: ignore[return-value]


async def _report(
    gateway: _ReportingGateway,
    *,
    transaction_repository,
    user_repository,
    uow,
    gateway_repository,
    purchase_dispatch,
    gateway_type: PaymentGatewayType = PaymentGatewayType.YOOKASSA,
    client_ip: str = "",
) -> RecordingEventPublisher:  # type: ignore[no-untyped-def]
    publisher = RecordingEventPublisher()
    use_case = HandlePaymentWebhookUseCase(
        transaction_repository,
        gateway_repository,
        _FixedFactory(gateway),
        user_repository,
        publisher,
        uow,
        purchase_dispatch,
    )
    await use_case.system(
        HandleWebhookDto(
            gateway_type=gateway_type,
            request=WebhookRequest(body=b"{}", headers={}, client_ip=client_ip),
        )
    )
    return publisher


async def _order(
    transaction_repository,
    uow,
    user_id,
    plan_id,
    *,
    status,
    source=DiscountSource.NONE,
    promocode_id=None,
):  # type: ignore[no-untyped-def]
    async with uow:
        order = await transaction_repository.create(
            _pending_order(
                user_id=user_id, plan_id=plan_id, source=source, promocode_id=promocode_id
            )
        )
        if status is not TransactionStatus.PENDING:
            await transaction_repository.mark_status_if(
                order.id, status, current=frozenset({TransactionStatus.PENDING})
            )
    return order


def _refunded(amount: Optional[str] = None, currency: Optional[str] = None) -> WebhookSignal:
    return WebhookSignal(
        reference="gated-ref",
        claims_paid=False,
        reported_status=TransactionStatus.REFUNDED,
        refund_amount=Decimal(amount) if amount is not None else None,
        refund_currency=currency,
    )


@pytest.mark.parametrize(
    ("amount", "currency"),
    [(None, None), ("500", "RUB"), ("5", "USD")],
    ids=["amount-unknown", "exactly-the-price", "other-currency"],
)
async def test_full_refund_marks_order_refunded_and_publishes_refund(
    amount,
    currency,
    transaction_repository,
    user_repository,
    uow,
    user_id,
    plan_id,
    gateway_repository,
    purchase_dispatch,
) -> None:  # type: ignore[no-untyped-def]
    order = await _order(
        transaction_repository, uow, user_id, plan_id, status=TransactionStatus.PAID
    )

    publisher = await _report(
        _ReportingGateway(_refunded(amount, currency)),
        transaction_repository=transaction_repository,
        user_repository=user_repository,
        uow=uow,
        gateway_repository=gateway_repository,
        purchase_dispatch=purchase_dispatch,
    )

    assert (await transaction_repository.get_by_id(order.id)).status is TransactionStatus.REFUNDED
    [event] = publisher.events
    assert isinstance(event, TransactionRefundedEvent)
    assert event.order_id == order.id
    assert event.payment_key == order.idempotency_key
    assert Decimal(event.amount) == order.final_price


async def test_partial_refund_keeps_order_paid(
    transaction_repository,
    user_repository,
    uow,
    user_id,
    plan_id,
    gateway_repository,
    purchase_dispatch,
) -> None:
    order = await _order(
        transaction_repository, uow, user_id, plan_id, status=TransactionStatus.PAID
    )

    publisher = await _report(
        _ReportingGateway(_refunded("499.99", "RUB")),
        transaction_repository=transaction_repository,
        user_repository=user_repository,
        uow=uow,
        gateway_repository=gateway_repository,
        purchase_dispatch=purchase_dispatch,
    )

    assert (await transaction_repository.get_by_id(order.id)).status is TransactionStatus.PAID
    [event] = publisher.events
    assert isinstance(event, TransactionPartiallyRefundedEvent)
    assert event.amount == "499.99"


async def test_refund_the_provider_api_disagrees_with_is_ignored(
    transaction_repository,
    user_repository,
    uow,
    user_id,
    plan_id,
    gateway_repository,
    purchase_dispatch,
) -> None:
    order = await _order(
        transaction_repository, uow, user_id, plan_id, status=TransactionStatus.PAID
    )

    publisher = await _report(
        _ReportingGateway(_refunded(), disagrees=True),
        transaction_repository=transaction_repository,
        user_repository=user_repository,
        uow=uow,
        gateway_repository=gateway_repository,
        purchase_dispatch=purchase_dispatch,
    )

    assert (await transaction_repository.get_by_id(order.id)).status is TransactionStatus.PAID
    assert publisher.events == []


async def test_refund_for_an_unpaid_order_is_ignored(
    transaction_repository,
    user_repository,
    uow,
    user_id,
    plan_id,
    gateway_repository,
    purchase_dispatch,
) -> None:
    order = await _order(
        transaction_repository, uow, user_id, plan_id, status=TransactionStatus.PENDING
    )

    publisher = await _report(
        _ReportingGateway(_refunded()),
        transaction_repository=transaction_repository,
        user_repository=user_repository,
        uow=uow,
        gateway_repository=gateway_repository,
        purchase_dispatch=purchase_dispatch,
    )

    assert (await transaction_repository.get_by_id(order.id)).status is TransactionStatus.PENDING
    assert publisher.events == []


async def _discounted_order(
    transaction_repository, user_repository, promocode_repository, uow, user_id, plan_id, *, status
):  # type: ignore[no-untyped-def]
    async with uow:
        await user_repository.update_fields(user_id, UpdateUserDto(purchase_discount=0))
        promocode = await promocode_repository.create(
            CreatePromocodeDto(
                code="GATED20", reward_type=PromocodeRewardType.PURCHASE_DISCOUNT, reward=20
            )
        )
    return await _order(
        transaction_repository,
        uow,
        user_id,
        plan_id,
        status=status,
        source=DiscountSource.PURCHASE,
        promocode_id=promocode.id,
    )


async def test_cancel_of_a_pending_order_gives_its_discount_back(
    transaction_repository,
    user_repository,
    uow,
    user_id,
    plan_id,
    gateway_repository,
    promocode_repository,
    purchase_dispatch,
) -> None:
    order = await _discounted_order(
        transaction_repository,
        user_repository,
        promocode_repository,
        uow,
        user_id,
        plan_id,
        status=TransactionStatus.PENDING,
    )

    publisher = await _report(
        _ReportingGateway(
            WebhookSignal(
                reference="gated-ref",
                claims_paid=False,
                reported_status=TransactionStatus.CANCELED,
            )
        ),
        transaction_repository=transaction_repository,
        user_repository=user_repository,
        uow=uow,
        gateway_repository=gateway_repository,
        purchase_dispatch=purchase_dispatch,
    )

    assert (await transaction_repository.get_by_id(order.id)).status is TransactionStatus.CANCELED
    assert (await user_repository.find_by_id(user_id)).purchase_discount == 20
    [event] = publisher.events
    assert isinstance(event, TransactionCanceledEvent)


async def test_failure_after_a_cancel_does_not_give_the_discount_back_again(
    transaction_repository,
    user_repository,
    uow,
    user_id,
    plan_id,
    gateway_repository,
    promocode_repository,
    purchase_dispatch,
) -> None:
    order = await _discounted_order(
        transaction_repository,
        user_repository,
        promocode_repository,
        uow,
        user_id,
        plan_id,
        status=TransactionStatus.CANCELED,
    )

    publisher = await _report(
        _ReportingGateway(
            WebhookSignal(
                reference="gated-ref",
                claims_paid=False,
                reported_status=TransactionStatus.FAILED,
            )
        ),
        transaction_repository=transaction_repository,
        user_repository=user_repository,
        uow=uow,
        gateway_repository=gateway_repository,
        purchase_dispatch=purchase_dispatch,
    )

    assert (await transaction_repository.get_by_id(order.id)).status is TransactionStatus.FAILED
    assert (await user_repository.find_by_id(user_id)).purchase_discount == 0
    assert publisher.events == []


async def test_gateway_with_an_allowlist_and_no_ip_switch_checks_the_source(
    user_repository, transaction_repository, uow, gateway_repository, purchase_dispatch
) -> None:
    gateway = _ReportingGateway(None, trusted_networks=("10.0.0.0/8",))

    with pytest.raises(PermissionDeniedError):
        await _report(
            gateway,
            transaction_repository=transaction_repository,
            user_repository=user_repository,
            uow=uow,
            gateway_repository=gateway_repository,
            purchase_dispatch=purchase_dispatch,
            gateway_type=PaymentGatewayType.PLATEGA,
            client_ip="203.0.113.7",
        )
    await _report(
        gateway,
        transaction_repository=transaction_repository,
        user_repository=user_repository,
        uow=uow,
        gateway_repository=gateway_repository,
        purchase_dispatch=purchase_dispatch,
        gateway_type=PaymentGatewayType.PLATEGA,
        client_ip="10.0.0.1",
    )


async def test_adapter_parse_error_becomes_a_gateway_error(
    user_repository, transaction_repository, uow, gateway_repository, purchase_dispatch
) -> None:
    with pytest.raises(PaymentGatewayError):
        await _report(
            _ReportingGateway(None, parse_error=KeyError("id")),
            transaction_repository=transaction_repository,
            user_repository=user_repository,
            uow=uow,
            gateway_repository=gateway_repository,
            purchase_dispatch=purchase_dispatch,
        )


async def test_refund_for_an_unknown_order_is_ignored(
    transaction_repository, user_repository, uow, gateway_repository, purchase_dispatch
) -> None:
    publisher = await _report(
        _ReportingGateway(_refunded()),
        transaction_repository=transaction_repository,
        user_repository=user_repository,
        uow=uow,
        gateway_repository=gateway_repository,
        purchase_dispatch=purchase_dispatch,
    )

    assert publisher.events == []
