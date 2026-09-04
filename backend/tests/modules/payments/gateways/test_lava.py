import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

import app.modules.payments.gateways.lava as lava_module
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
from app.modules.payments.gateways.lava import LavaGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"shop_id": "shop-1", "secret_key": "lava-secret", "webhook_secret": "lava-webhook"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/lava"
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
        "gateway_type": PaymentGatewayType.LAVA,
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


def _gateway() -> LavaGateway:
    return LavaGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(lava_module, "http_client", httpx.AsyncClient(transport=handler))


def _webhook(body: dict[str, object], secret: str = "lava-webhook") -> WebhookRequest:
    raw = json.dumps(body).encode()
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return WebhookRequest(body=raw, headers={"authorization": signature}, query={}, client_ip=None)


async def test_create_payment_signs_the_exact_bytes_sent_and_returns_the_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["content"] = request.content
        captured["sign"] = request.headers.get("signature")
        return httpx.Response(
            200,
            json={"status": "success", "data": {"id": "lava-1", "url": "https://lava.ru/pay/x"}},
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://lava.ru/pay/x"
    assert intent.provider_payment_id == "lava-1"
    expected_sig = hmac.new(b"lava-secret", captured["content"], hashlib.sha256).hexdigest()  # type: ignore[arg-type]
    assert captured["sign"] == expected_sig
    body = json.loads(captured["content"])  # type: ignore[arg-type]
    assert body["orderId"] == "order-key-1"
    assert body["shopId"] == "shop-1"


async def test_create_payment_raises_on_an_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "error", "error": "bad shop"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(_order())


async def test_parse_webhook_success_status_returns_result() -> None:
    body = {"invoice_id": "lava-1", "order_id": "order-key-1", "status": "success"}

    result = await _gateway().parse_webhook(_webhook(body))

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.provider_payment_id == "lava-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_accepts_the_canonical_sorted_json_fallback() -> None:
    body = {"order_id": "order-key-1", "invoice_id": "lava-1", "status": "success"}
    raw = json.dumps(body).encode()  # not the canonical sorted form
    canonical = json.dumps(dict(sorted(body.items())), separators=(",", ":")).encode()
    signature = hmac.new(b"lava-webhook", canonical, hashlib.sha256).hexdigest()
    request = WebhookRequest(
        body=raw, headers={"authorization": signature}, query={}, client_ip=None
    )

    result = await _gateway().parse_webhook(request)

    assert result is not None
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_invalid_signature_raises() -> None:
    body = json.dumps({"order_id": "order-key-1", "status": "success"}).encode()
    request = WebhookRequest(
        body=body, headers={"authorization": "deadbeef"}, query={}, client_ip=None
    )
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_missing_signature_raises() -> None:
    body = json.dumps({"order_id": "order-key-1", "status": "success"}).encode()
    request = WebhookRequest(body=body, headers={}, query={}, client_ip=None)
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_pending_status_is_a_noop() -> None:
    body = {"invoice_id": "lava-1", "order_id": "order-key-1", "status": "pending"}
    result = await _gateway().parse_webhook(_webhook(body))
    assert result is None
