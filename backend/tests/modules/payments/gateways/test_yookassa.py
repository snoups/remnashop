import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

import app.modules.payments.gateways.yookassa as yookassa_module
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PaymentOrderStatus,
    PurchaseType,
)
from app.core.utils.time import datetime_now
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.yookassa import YooKassaGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"shop_id": "1000", "api_key": "test_key"}


def _order(**overrides: object) -> PaymentOrderDto:
    defaults: dict[str, object] = {
        "id": 1,
        "user_id": 1,
        "plan_id": 1,
        "plan_snapshot": make_plan_snapshot(plan_id=1),
        "duration_days": 30,
        "currency": Currency.RUB,
        "purchase_type": PurchaseType.NEW,
        "gateway_type": PaymentGatewayType.YOOKASSA,
        "status": PaymentOrderStatus.PENDING,
        "base_price": Decimal("500"),
        "discount_percent": 0,
        "discount_source": DiscountSource.NONE,
        "final_price": Decimal("500"),
        "idempotency_key": "order-key-1",
        "expires_at": datetime_now() + timedelta(minutes=30),
    }
    defaults.update(overrides)
    return PaymentOrderDto(**defaults)  # type: ignore[arg-type]


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    # The gateway reuses one module-level client rather than constructing one
    # per call -- swap that instance out for the duration of the test instead
    # of patching the AsyncClient constructor.
    monkeypatch.setattr(yookassa_module, "_client", httpx.AsyncClient(transport=handler))


async def test_create_payment_sends_idempotence_key_and_returns_id_and_confirmation_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200,
            json={
                "id": "yk-payment-1",
                "confirmation": {"confirmation_url": "https://yookassa.ru/pay/1"},
            },
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))
    gateway = YooKassaGateway()

    external_payment_id, url = await gateway.create_payment(_order(), _SETTINGS)

    assert external_payment_id == "yk-payment-1"
    assert url == "https://yookassa.ru/pay/1"
    request = captured["request"]
    assert request.headers["Idempotence-Key"] == "order-key-1"
    assert request.headers["Authorization"].startswith("Basic ")


async def _create_payment_body(
    monkeypatch: pytest.MonkeyPatch, order: PaymentOrderDto, settings: dict[str, str]
) -> dict[str, object]:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "yk-payment-1",
                "confirmation": {"confirmation_url": "https://yookassa.ru/pay/1"},
            },
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))
    await YooKassaGateway().create_payment(order, settings)
    return captured["body"]  # type: ignore[return-value]


async def test_receipt_is_sent_when_both_email_and_vat_code_are_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = await _create_payment_body(
        monkeypatch,
        _order(customer_email="buyer@example.com"),
        {**_SETTINGS, "vat_code": "1"},
    )

    receipt = body["receipt"]
    assert receipt["customer"]["email"] == "buyer@example.com"  # type: ignore[index,call-overload]
    assert receipt["items"][0]["vat_code"] == 1  # type: ignore[index,call-overload]


async def test_no_receipt_when_vat_code_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # A receipt without vat_code is a 400 from YooKassa -- no receipt at all
    # is the only working request.
    body = await _create_payment_body(
        monkeypatch, _order(customer_email="buyer@example.com"), _SETTINGS
    )

    assert "receipt" not in body


async def test_no_receipt_when_customer_email_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = await _create_payment_body(monkeypatch, _order(), {**_SETTINGS, "vat_code": "1"})

    assert "receipt" not in body


async def test_verify_payment_true_only_on_succeeded_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "yk-payment-1", "status": "succeeded"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))
    gateway = YooKassaGateway()

    assert await gateway.verify_payment("yk-payment-1", _SETTINGS) is True


async def test_verify_payment_false_on_pending_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "yk-payment-1", "status": "pending"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))
    gateway = YooKassaGateway()

    assert await gateway.verify_payment("yk-payment-1", _SETTINGS) is False


async def test_verify_payment_never_trusts_a_claimed_status_it_did_not_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Even if some future caller mistakenly passed a "succeeded" hint through
    # settings/kwargs, verify_payment has no such parameter -- it only ever
    # reads the field the provider itself returned in this response body.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "yk-payment-1", "status": "canceled"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))
    gateway = YooKassaGateway()

    assert await gateway.verify_payment("yk-payment-1", _SETTINGS) is False
