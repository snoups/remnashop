import base64
import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

import app.modules.payments.gateways.paypear as paypear_module
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
from app.modules.payments.gateways.paypear import PayPearGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"shop_id": "shop-1", "secret_key": "pp-secret"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/paypear"
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
        "gateway_type": PaymentGatewayType.PAYPEAR,
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


def _gateway() -> PayPearGateway:
    return PayPearGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(paypear_module, "http_client", httpx.AsyncClient(transport=handler))


def _sign(body: dict[str, object], secret: str = "pp-secret") -> str:
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _webhook_body(obj: dict[str, object], event: str = "payment.confirmed") -> dict[str, object]:
    body: dict[str, object] = {"event": event, "object": obj}
    body["signature"] = _sign(body)
    return body


def _webhook(body: dict[str, object], client_ip: str | None = None) -> WebhookRequest:
    return WebhookRequest(body=json.dumps(body).encode(), headers={}, query={}, client_ip=client_ip)


async def test_create_payment_sends_basic_auth_and_returns_the_confirmation_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        captured["idempotence"] = request.headers.get("idempotence-key")
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": "pp-1",
                    "confirmation": {"confirmation_url": "https://paypear.ru/pay/x"},
                },
            },
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://paypear.ru/pay/x"
    assert intent.provider_payment_id == "pp-1"
    expected_auth = "Basic " + base64.b64encode(b"shop-1:pp-secret").decode()
    assert captured["auth"] == expected_auth
    assert captured["idempotence"]
    assert captured["body"]["order_id"] == "order-key-1"  # type: ignore[index,call-overload]


async def test_create_payment_raises_when_api_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": False, "message": "bad shop"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(_order())


async def test_parse_webhook_confirmed_event_returns_result() -> None:
    body = _webhook_body({"id": "pp-1", "order_id": "order-key-1", "status": "CONFIRMED"})

    result = await _gateway().parse_webhook(_webhook(body))

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_trusts_the_documented_ip_when_signature_is_absent() -> None:
    body = {
        "event": "payment.confirmed",
        "object": {"id": "pp-1", "order_id": "order-key-1", "status": "CONFIRMED"},
    }

    result = await _gateway().parse_webhook(_webhook(body, client_ip="158.160.85.101"))

    assert result is not None
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_rejects_bad_signature_and_untrusted_ip() -> None:
    body = {
        "event": "payment.confirmed",
        "object": {"id": "pp-1", "order_id": "order-key-1", "status": "CONFIRMED"},
        "signature": "deadbeef",
    }
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(body, client_ip="1.2.3.4"))


async def test_parse_webhook_non_confirmed_is_a_noop() -> None:
    body = _webhook_body(
        {"id": "pp-1", "order_id": "order-key-1", "status": "NEW"}, event="payment.created"
    )

    result = await _gateway().parse_webhook(_webhook(body))

    assert result is None
