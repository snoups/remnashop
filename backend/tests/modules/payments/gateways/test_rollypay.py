import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

import app.modules.payments.gateways.rollypay as rollypay_module
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
from app.modules.payments.gateways.rollypay import RollyPayGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"api_key": "rp-api-key", "signing_secret": "rp-signing-secret"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/rollypay"
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
        "gateway_type": PaymentGatewayType.ROLLYPAY,
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


def _gateway() -> RollyPayGateway:
    return RollyPayGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(rollypay_module, "_client", httpx.AsyncClient(transport=handler))


def _signed_webhook(
    body: dict[str, object], timestamp: str = "1700000000", secret: str = "rp-signing-secret"
) -> WebhookRequest:
    raw = json.dumps(body).encode()
    message = f"{timestamp}.{raw.decode('utf-8')}"
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return WebhookRequest(
        body=raw,
        headers={"x-signature": signature, "x-timestamp": timestamp},
        query={},
        client_ip=None,
    )


async def test_create_payment_sends_api_key_and_order_ref_and_returns_pay_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["api_key"] = request.headers.get("x-api-key")
        captured["nonce"] = request.headers.get("x-nonce")
        return httpx.Response(
            200, json={"payment_id": "rp-1", "pay_url": "https://rollypay.io/pay/x"}
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://rollypay.io/pay/x"
    assert intent.provider_payment_id == "rp-1"
    assert captured["api_key"] == "rp-api-key"
    assert captured["nonce"]
    body = captured["body"]
    assert body["order_id"] == "order-key-1"  # type: ignore[index,call-overload]
    assert body["payment_currency"] == "RUB"  # type: ignore[index,call-overload]


async def test_create_payment_raises_when_api_returns_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": "invalid amount"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(_order())


async def test_parse_webhook_paid_event_returns_result_via_order_id() -> None:
    result = await _gateway().parse_webhook(
        _signed_webhook(
            {
                "event_type": "payment.paid",
                "payment_id": "rp-1",
                "order_id": "order-key-1",
                "status": "paid",
            }
        )
    )

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.provider_payment_id == "rp-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_invalid_signature_raises() -> None:
    body = json.dumps({"payment_id": "rp-1", "status": "paid"}).encode()
    request = WebhookRequest(
        body=body,
        headers={"x-signature": "deadbeef", "x-timestamp": "1700000000"},
        query={},
        client_ip=None,
    )
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_missing_signature_headers_raises() -> None:
    body = json.dumps({"payment_id": "rp-1", "status": "paid"}).encode()
    request = WebhookRequest(body=body, headers={}, query={}, client_ip=None)
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_non_paid_status_is_a_noop() -> None:
    result = await _gateway().parse_webhook(
        _signed_webhook(
            {"event_type": "payment.created", "payment_id": "rp-1", "status": "created"}
        )
    )
    assert result is None


async def test_parse_webhook_missing_required_fields_is_a_noop_not_an_error() -> None:
    # RollyPay retries with exponential backoff on anything but 200 -- a
    # shape we can't act on is a no-op ack, not a rejection.
    result = await _gateway().parse_webhook(_signed_webhook({"event_type": "payment.paid"}))
    assert result is None
