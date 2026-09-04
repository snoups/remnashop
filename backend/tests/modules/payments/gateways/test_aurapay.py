import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

import app.modules.payments.gateways.aurapay as aurapay_module
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
from app.modules.payments.gateways.aurapay import AuraPayGateway
from app.modules.payments.gateways.base import WebhookRequest
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"api_key": "ap-key", "shop_id": "shop-1", "secret_key": "ap-secret"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/aurapay"
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
        "gateway_type": PaymentGatewayType.AURAPAY,
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


def _gateway() -> AuraPayGateway:
    return AuraPayGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(aurapay_module, "http_client", httpx.AsyncClient(transport=handler))


def _sign(payload: dict[str, object], secret: str = "ap-secret") -> str:
    concatenated = "".join(
        str(payload[key]) if payload[key] is not None else "" for key in sorted(payload)
    )
    return hmac.new(secret.encode(), concatenated.encode(), hashlib.sha256).hexdigest()


def _signed_webhook(body: dict[str, object]) -> WebhookRequest:
    raw = json.dumps(body).encode()
    return WebhookRequest(body=raw, headers={"x-signature": _sign(body)}, query={}, client_ip=None)


async def test_create_payment_sends_headers_and_returns_the_nested_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["api_key"] = request.headers.get("x-apikey")
        captured["shop_id"] = request.headers.get("x-shopid")
        return httpx.Response(
            200, json={"id": "ap-1", "payment_data": {"url": "https://app.aurapay.tech/pay/x"}}
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://app.aurapay.tech/pay/x"
    assert intent.provider_payment_id == "ap-1"
    assert captured["api_key"] == "ap-key"
    assert captured["shop_id"] == "shop-1"
    body = captured["body"]
    assert body["order_id"] == "order-key-1"  # type: ignore[index,call-overload]


async def test_create_payment_raises_when_url_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "ap-1", "payment_data": {}})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(_order())


async def test_parse_webhook_paid_status_returns_result() -> None:
    result = await _gateway().parse_webhook(
        _signed_webhook({"id": "ap-1", "order_id": "order-key-1", "status": "PAID"})
    )

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_invalid_signature_raises() -> None:
    body = {"id": "ap-1", "order_id": "order-key-1", "status": "PAID"}
    request = WebhookRequest(
        body=json.dumps(body).encode(),
        headers={"x-signature": "deadbeef"},
        query={},
        client_ip=None,
    )
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_missing_signature_raises() -> None:
    body = {"id": "ap-1", "order_id": "order-key-1", "status": "PAID"}
    request = WebhookRequest(body=json.dumps(body).encode(), headers={}, query={}, client_ip=None)
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_non_paid_status_is_a_noop() -> None:
    result = await _gateway().parse_webhook(
        _signed_webhook({"id": "ap-1", "order_id": "order-key-1", "status": "PENDING"})
    )
    assert result is None
