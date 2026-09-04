import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

import app.modules.payments.gateways.valutix as valutix_module
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
from app.modules.payments.gateways.valutix import ValutixGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"api_key": "valutix-token"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/valutix"
_RETURN_URL = "https://shop.example"


def _order(**overrides: object) -> PaymentOrderDto:
    defaults: dict[str, object] = {
        "id": 1,
        "user_id": 1,
        "plan_id": 1,
        "plan_snapshot": make_plan_snapshot(plan_id=1),
        "duration_days": 30,
        "currency": Currency.USD,
        "purchase_type": PurchaseType.NEW,
        "gateway_type": PaymentGatewayType.VALUTIX,
        "status": PaymentOrderStatus.PENDING,
        "base_price": Decimal("10"),
        "discount_percent": 0,
        "discount_source": DiscountSource.NONE,
        "final_price": Decimal("10"),
        "idempotency_key": "order-key-1",
        "expires_at": datetime_now() + timedelta(minutes=30),
    }
    defaults.update(overrides)
    return PaymentOrderDto(**defaults)  # type: ignore[arg-type]


def _gateway() -> ValutixGateway:
    return ValutixGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(valutix_module, "http_client", httpx.AsyncClient(transport=handler))


def _signed_webhook(body: dict[str, object], token: str = "valutix-token") -> WebhookRequest:
    raw = json.dumps(body).encode()
    signature = hmac.new(token.encode(), raw, hashlib.sha512).hexdigest()
    return WebhookRequest(body=raw, headers={"x-signature": signature}, query={}, client_ip=None)


async def test_create_payment_sends_token_header_and_returns_link_and_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["token"] = request.headers.get("x-api-token")
        return httpx.Response(200, json={"id": "vx-1", "paymentLink": "https://pay.valutix.kz/x"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://pay.valutix.kz/x"
    assert intent.provider_payment_id == "vx-1"
    assert captured["token"] == "valutix-token"
    body = captured["body"]
    assert body["externalId"] == "order-key-1"  # type: ignore[index,call-overload]
    assert body["callbackUrl"] == _WEBHOOK_URL  # type: ignore[index,call-overload]


async def test_parse_webhook_completed_status_returns_paid_via_provider_id() -> None:
    result = await _gateway().parse_webhook(_signed_webhook({"id": "vx-1", "status": "COMPLETED"}))

    assert result is not None
    assert result.reference == ""
    assert result.provider_payment_id == "vx-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_invalid_signature_raises() -> None:
    request = WebhookRequest(
        body=json.dumps({"id": "vx-1", "status": "COMPLETED"}).encode(),
        headers={"x-signature": "deadbeef"},
        query={},
        client_ip=None,
    )
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_missing_signature_raises() -> None:
    request = WebhookRequest(
        body=json.dumps({"id": "vx-1", "status": "COMPLETED"}).encode(),
        headers={},
        query={},
        client_ip=None,
    )
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_pending_status_is_a_noop() -> None:
    result = await _gateway().parse_webhook(_signed_webhook({"id": "vx-1", "status": "PENDING"}))
    assert result is None
