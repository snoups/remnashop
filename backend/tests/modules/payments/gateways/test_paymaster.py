import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

import app.modules.payments.gateways.paymaster as paymaster_module
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PaymentOrderStatus,
    PurchaseType,
)
from app.core.exceptions import PaymentGatewayError
from app.core.utils.time import datetime_now
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import WebhookRequest
from app.modules.payments.gateways.paymaster import PayMasterGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"merchant_id": "merchant-1", "api_key": "bearer-token"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/paymaster"
_RETURN_URL = "https://shop.example"


def _order(**overrides: object) -> PaymentOrderDto:
    defaults: dict[str, object] = {
        "id": 1,
        "user_id": 1,
        "plan_id": 1,
        "plan_snapshot": make_plan_snapshot(plan_id=1),
        "duration_days": 30,
        "currency": Currency.RUB,
        "purchase_type": PurchaseType.NEW,
        "gateway_type": PaymentGatewayType.PAYMASTER,
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


def _gateway() -> PayMasterGateway:
    return PayMasterGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(paymaster_module, "_client", httpx.AsyncClient(transport=handler))


def _webhook(body: dict[str, object]) -> WebhookRequest:
    return WebhookRequest(body=json.dumps(body).encode(), headers={}, query={}, client_ip=None)


async def test_create_payment_sends_the_idempotency_key_and_returns_the_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["headers"] = request.headers
        return httpx.Response(200, json={"paymentId": "pm-1", "url": "https://paymaster.ru/pay/1"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://paymaster.ru/pay/1"
    assert intent.provider_payment_id == "pm-1"
    headers = captured["headers"]
    assert headers["authorization"] == "Bearer bearer-token"  # type: ignore[index]
    assert headers["idempotency-key"] == "order-key-1"  # type: ignore[index]
    body = captured["body"]
    assert body["merchantId"] == "merchant-1"  # type: ignore[index,call-overload]
    assert body["protocol"]["callbackUrl"] == _WEBHOOK_URL  # type: ignore[index,call-overload]


async def test_parse_webhook_settled_status_returns_paid() -> None:
    result = await _gateway().parse_webhook(_webhook({"id": "pm-1", "status": "Settled"}))

    assert result is not None
    assert result.reference == ""
    assert result.provider_payment_id == "pm-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_cancelled_status_returns_none() -> None:
    result = await _gateway().parse_webhook(_webhook({"id": "pm-1", "status": "Cancelled"}))

    assert result is None


async def test_parse_webhook_missing_id_raises() -> None:
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook({"status": "Settled"}))
