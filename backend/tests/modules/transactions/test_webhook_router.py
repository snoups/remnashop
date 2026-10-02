from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from typing import AsyncIterator, Optional

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.db.models import EventOutboxEntry
from app.core.di.providers import get_core_providers
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseType,
    TransactionStatus,
)
from app.core.utils.time import datetime_now
from app.modules.providers import get_module_providers
from app.modules.subscriptions import PurchaseSubscriptionDispatch
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.gateways.base import ProviderPayment, WebhookAck, WebhookSignal
from app.modules.transactions.gateways.registry import GATEWAY_REGISTRY
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.subscriptions.factories import make_plan_snapshot

_CONFIRMED = ProviderPayment(
    paid=True, amount=Decimal("500"), reference="order-ref", provider_payment_id="yk-2"
)


class _StubGateway:
    trusted_networks: tuple[str, ...] = ()

    def __init__(
        self,
        *,
        signal: Optional[WebhookSignal],
        payment: Optional[ProviderPayment] = _CONFIRMED,
        confirm_exc: Optional[BaseException] = None,
        parse_exc: Optional[BaseException] = None,
        ack: WebhookAck = WebhookAck(),
    ) -> None:
        self._signal = signal
        self._payment = payment
        self._confirm_exc = confirm_exc
        self._parse_exc = parse_exc
        self._ack = ack
        self.confirm_calls = 0

    async def parse_webhook(self, request: object) -> Optional[WebhookSignal]:
        if self._parse_exc is not None:
            raise self._parse_exc
        return self._signal

    async def confirm(self, order: object, signal: object) -> Optional[ProviderPayment]:
        self.confirm_calls += 1
        if self._confirm_exc is not None:
            raise self._confirm_exc
        return self._payment

    def webhook_ack(self, signal: object) -> WebhookAck:
        return self._ack


def _paid_signal(reference: str, provider_payment_id: Optional[str] = None) -> WebhookSignal:
    return WebhookSignal(
        reference=reference, claims_paid=True, provider_payment_id=provider_payment_id
    )


def _install_stub(monkeypatch: pytest.MonkeyPatch, stub: _StubGateway) -> None:
    monkeypatch.setattr(
        "app.modules.transactions.gateways.factory.PaymentGatewayFactory.build",
        lambda self, gateway_type, settings: stub,
    )


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


class _DispatchProvider(Provider):
    scope = Scope.APP

    def __init__(self, purchase_dispatch: RecordingDispatch) -> None:
        super().__init__()
        self._purchase_dispatch = purchase_dispatch

    @provide
    def purchase_dispatch(self) -> PurchaseSubscriptionDispatch:
        return self._purchase_dispatch


@pytest.fixture
def purchase_dispatch() -> RecordingDispatch:
    return RecordingDispatch()


@pytest.fixture
async def test_container(
    session: AsyncSession, config: AppConfig, purchase_dispatch: RecordingDispatch
) -> AsyncIterator[AsyncContainer]:
    providers = [
        *get_core_providers(),
        *get_module_providers(),
        _DispatchProvider(purchase_dispatch),
        _TestSessionProvider(session),
    ]
    container = make_async_container(*providers, context={AppConfig: config})
    yield container
    await container.close()


@pytest.fixture
async def client(
    config: AppConfig, test_container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    app = get_app(config)
    setup_dishka(test_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


def _pending_order_dto(*, user_id: int, plan_id: int, idempotency_key: str) -> CreateTransactionDto:
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


async def test_unknown_gateway_type_returns_404(client) -> None:
    response = await client.post("/api/v1/payments/not-a-gateway", content=b"{}")
    assert response.status_code == 404


async def test_gateway_type_with_no_adapter_returns_404(client, monkeypatch) -> None:
    # Real PaymentGatewayFactory.build (not the stub) -- every currently
    # defined PaymentGatewayType has an adapter, so remove one to exercise
    # the miss.
    monkeypatch.delitem(GATEWAY_REGISTRY, PaymentGatewayType.YOOKASSA)
    response = await client.post("/api/v1/payments/yookassa", content=b"{}")
    assert response.status_code == 404


async def test_webhook_order_not_found_returns_200(client, monkeypatch) -> None:
    _install_stub(monkeypatch, _StubGateway(signal=_paid_signal("missing")))
    response = await client.post("/api/v1/payments/yookassa", content=b"{}")
    assert response.status_code == 200


async def test_webhook_not_claiming_payment_never_calls_confirm(
    client, transaction_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        await transaction_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-key-0")
        )
    stub = _StubGateway(signal=WebhookSignal(reference="wh-key-0", claims_paid=False))
    _install_stub(monkeypatch, stub)

    response = await client.post("/api/v1/payments/yookassa", content=b"{}")

    assert response.status_code == 200
    assert stub.confirm_calls == 0


async def test_webhook_returns_the_gateway_ack(client, monkeypatch) -> None:
    ack = WebhookAck(body='{"status": true}', media_type="application/json")
    _install_stub(monkeypatch, _StubGateway(signal=None, ack=ack))

    response = await client.post("/api/v1/payments/yookassa", content=b"{}")

    assert response.status_code == 200
    assert response.text == '{"status": true}'
    assert response.headers["content-type"].startswith("application/json")


async def test_webhook_already_paid_order_is_a_noop_and_never_confirms(
    client, transaction_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-key-1")
        )
        await transaction_repository.mark_status(
            order.id, TransactionStatus.PAID, external_payment_id="yk-1"
        )
    stub = _StubGateway(signal=_paid_signal("wh-key-1"))
    _install_stub(monkeypatch, stub)

    response = await client.post("/api/v1/payments/yookassa", content=b"{}")

    assert response.status_code == 200
    assert stub.confirm_calls == 0


async def test_webhook_confirmed_payment_marks_paid_and_dispatches_purchase(
    client, transaction_repository, uow, user_id, plan_id, monkeypatch, purchase_dispatch
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-key-2")
        )
    _install_stub(monkeypatch, _StubGateway(signal=_paid_signal("wh-key-2")))
    response = await client.post("/api/v1/payments/yookassa", content=b"{}")

    assert response.status_code == 200
    fetched = await transaction_repository.get_by_id(order.id)
    assert fetched.status is TransactionStatus.PAID
    assert fetched.external_payment_id == "yk-2"
    assert len(purchase_dispatch.messages) == 1
    assert purchase_dispatch.messages[0]["idempotency_key"] == "wh-key-2"
    assert purchase_dispatch.messages[0]["base_price"] == "500.00"


async def test_webhook_confirmed_test_payment_marks_paid_without_provisioning(
    client, transaction_repository, uow, user_id, plan_id, monkeypatch, purchase_dispatch
) -> None:
    async with uow:
        order = await transaction_repository.create(
            replace(
                _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-test"),
                is_test=True,
            )
        )
    _install_stub(monkeypatch, _StubGateway(signal=_paid_signal("wh-test")))
    response = await client.post("/api/v1/payments/yookassa", content=b"{}")

    assert response.status_code == 200
    assert (await transaction_repository.get_by_id(order.id)).status is TransactionStatus.PAID
    assert purchase_dispatch.messages == []
    assert await transaction_repository.count_paid_since(datetime_now() - timedelta(days=1)) == 0


async def test_webhook_unconfirmed_payment_returns_502_and_leaves_the_order_pending(
    client, transaction_repository, uow, user_id, plan_id, monkeypatch, purchase_dispatch
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-key-4")
        )
    _install_stub(monkeypatch, _StubGateway(signal=_paid_signal("wh-key-4"), payment=None))
    response = await client.post("/api/v1/payments/yookassa", content=b"{}")

    assert response.status_code == 502
    fetched = await transaction_repository.get_by_id(order.id)
    assert fetched.status is TransactionStatus.PENDING
    assert purchase_dispatch.messages == []


async def test_webhook_confirm_exception_returns_502(
    client, transaction_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        await transaction_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-key-3")
        )
    _install_stub(
        monkeypatch,
        _StubGateway(
            signal=_paid_signal("wh-key-3"),
            confirm_exc=ConnectionError("simulated network failure"),
        ),
    )

    response = await client.post("/api/v1/payments/yookassa", content=b"{}")
    assert response.status_code == 502


async def test_webhook_from_another_gateway_never_touches_the_order(
    client, transaction_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-key-5")
        )
    stub = _StubGateway(signal=_paid_signal("wh-key-5", "ym-1"))
    _install_stub(monkeypatch, stub)

    response = await client.post("/api/v1/payments/yoomoney", content=b"{}")

    assert response.status_code == 200
    fetched = await transaction_repository.get_by_id(order.id)
    assert fetched.status is TransactionStatus.PENDING
    assert stub.confirm_calls == 0


async def test_webhook_parse_error_returns_502(client, monkeypatch) -> None:
    _install_stub(
        monkeypatch,
        _StubGateway(signal=None, parse_exc=ValueError("adapter leaked a parse error")),
    )
    response = await client.post("/api/v1/payments/yookassa", content=b"{}")
    assert response.status_code == 502


def _canceled_signal(reference: str) -> WebhookSignal:
    return WebhookSignal(
        reference=reference, claims_paid=False, reported_status=TransactionStatus.CANCELED
    )


async def test_webhook_failure_marks_a_pending_order(
    client, transaction_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-fail-1")
        )
    stub = _StubGateway(signal=_canceled_signal("wh-fail-1"))
    _install_stub(monkeypatch, stub)

    response = await client.post("/api/v1/payments/yookassa", content=b"{}")

    assert response.status_code == 200
    assert stub.confirm_calls == 0
    fetched = await transaction_repository.get_by_id(order.id)
    assert fetched.status is TransactionStatus.CANCELED


async def test_webhook_failure_never_overwrites_a_paid_order(
    client, transaction_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-fail-2")
        )
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
    _install_stub(monkeypatch, _StubGateway(signal=_canceled_signal("wh-fail-2")))

    await client.post("/api/v1/payments/yookassa", content=b"{}")

    fetched = await transaction_repository.get_by_id(order.id)
    assert fetched.status is TransactionStatus.PAID


async def test_webhook_late_payment_on_a_canceled_order_is_still_honoured(
    client, transaction_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-fail-4")
        )
        await transaction_repository.mark_status(order.id, TransactionStatus.CANCELED)
    _install_stub(monkeypatch, _StubGateway(signal=_paid_signal("wh-fail-4")))

    response = await client.post("/api/v1/payments/yookassa", content=b"{}")

    assert response.status_code == 200
    fetched = await transaction_repository.get_by_id(order.id)
    assert fetched.status is TransactionStatus.PAID


async def test_webhook_refund_marks_only_a_paid_order_and_publishes_an_event(
    client, transaction_repository, uow, session, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        paid = await transaction_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-refund-1")
        )
        await transaction_repository.mark_status(paid.id, TransactionStatus.PAID)
        pending = await transaction_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-refund-2")
        )

    for key in ("wh-refund-1", "wh-refund-2"):
        signal = WebhookSignal(
            reference=key, claims_paid=False, reported_status=TransactionStatus.REFUNDED
        )
        _install_stub(monkeypatch, _StubGateway(signal=signal))
        await client.post("/api/v1/payments/yookassa", content=b"{}")

    assert (await transaction_repository.get_by_id(paid.id)).status is TransactionStatus.REFUNDED
    assert (await transaction_repository.get_by_id(pending.id)).status is TransactionStatus.PENDING
    events = (
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == "TransactionRefundedEvent"
            )
        )
    ).all()
    assert [event.payload["order_id"] for event in events] == [paid.id]


async def test_webhook_refunded_order_is_not_reprovisioned(
    client, transaction_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    # the provider still reports the original payment as paid after a refund;
    # re-confirming it would provision the order a second time
    async with uow:
        order = await transaction_repository.create(
            _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-key-refund")
        )
        await transaction_repository.mark_status(
            order.id, TransactionStatus.REFUNDED, external_payment_id="yk-refund"
        )
    stub = _StubGateway(signal=_paid_signal("wh-key-refund"))
    _install_stub(monkeypatch, stub)

    response = await client.post("/api/v1/payments/yookassa", content=b"{}")

    assert response.status_code == 200
    assert stub.confirm_calls == 0


_YOOKASSA_PAID_BODY = b'{"event": "payment.succeeded", "object": {"id": "yk-none", "metadata": {}}}'


async def test_yookassa_webhook_from_untrusted_ip_is_rejected(client) -> None:
    # the test client connects from 127.0.0.1, which is not a YooKassa network
    response = await client.post("/api/v1/payments/yookassa", content=_YOOKASSA_PAID_BODY)
    assert response.status_code == 403


async def test_yookassa_webhook_from_trusted_ip_is_accepted(client) -> None:
    # loopback peer = the reverse proxy, which appends the real client last
    response = await client.post(
        "/api/v1/payments/yookassa",
        content=_YOOKASSA_PAID_BODY,
        headers={"X-Forwarded-For": "6.6.6.6, 185.71.76.5"},
    )
    assert response.status_code == 200


async def test_yookassa_webhook_spoofed_forwarded_for_is_not_trusted(client) -> None:
    # only the rightmost entry is the proxy's own view of the peer
    response = await client.post(
        "/api/v1/payments/yookassa",
        content=_YOOKASSA_PAID_BODY,
        headers={"X-Forwarded-For": "185.71.76.5, 6.6.6.6"},
    )
    assert response.status_code == 403


async def test_yookassa_ip_check_can_be_switched_off(client, gateway_repository, uow) -> None:
    async with uow:
        await gateway_repository.update_settings(
            PaymentGatewayType.YOOKASSA, {"verify_ip": "false"}
        )

    response = await client.post("/api/v1/payments/yookassa", content=_YOOKASSA_PAID_BODY)

    assert response.status_code == 200


def _discounted_order_dto(
    *, user_id: int, plan_id: int, idempotency_key: str
) -> CreateTransactionDto:
    return replace(
        _pending_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key=idempotency_key),
        discount_percent=20,
        discount_source=DiscountSource.PURCHASE,
        final_price=Decimal("400"),
    )


async def test_provider_cancel_gives_back_the_purchase_discount_once(
    client, transaction_repository, user_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        await transaction_repository.create(
            _discounted_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-disc-1")
        )
    canceled = WebhookSignal(
        reference="wh-disc-1", claims_paid=False, reported_status=TransactionStatus.CANCELED
    )
    _install_stub(monkeypatch, _StubGateway(signal=canceled))

    await client.post("/api/v1/payments/yookassa", content=b"{}")
    assert (await user_repository.get_by_id(user_id)).purchase_discount == 20

    # spent again elsewhere; a repeated CANCELED must not hand it back a second time
    async with uow:
        assert await user_repository.spend_purchase_discount(user_id, 20)
    await client.post("/api/v1/payments/yookassa", content=b"{}")
    assert (await user_repository.get_by_id(user_id)).purchase_discount == 0


async def test_late_payment_for_a_canceled_discounted_order_is_not_fulfilled(
    client, transaction_repository, uow, user_id, plan_id, monkeypatch
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _discounted_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="wh-disc-2")
        )
        await transaction_repository.mark_status(order.id, TransactionStatus.CANCELED)
    stub = _StubGateway(signal=_paid_signal("wh-disc-2"))
    _install_stub(monkeypatch, stub)

    response = await client.post("/api/v1/payments/yookassa", content=b"{}")

    assert response.status_code == 200
    assert stub.confirm_calls == 0
    assert (await transaction_repository.get_by_id(order.id)).status is (TransactionStatus.CANCELED)
