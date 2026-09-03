import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

import app.modules.payments.gateways.riopay as riopay_module
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
from app.modules.payments.gateways.riopay import RioPayGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"api_token": "rio-token", "webhook_secret": "rio-webhook-secret"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/riopay"
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
        "gateway_type": PaymentGatewayType.RIOPAY,
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


def _gateway(settings: dict[str, str] = _SETTINGS) -> RioPayGateway:
    return RioPayGateway(settings=settings, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(riopay_module, "_client", httpx.AsyncClient(transport=handler))


def _sign(raw: bytes, secret: str = "rio-webhook-secret") -> str:
    return hmac.new(secret.encode(), raw, hashlib.sha512).hexdigest()


def _signed_webhook(body: dict[str, object], secret: str = "rio-webhook-secret") -> WebhookRequest:
    raw = json.dumps(body).encode()
    return WebhookRequest(
        body=raw, headers={"x-signature": _sign(raw, secret)}, query={}, client_ip=None
    )


async def test_create_payment_sends_the_token_and_returns_the_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["token"] = request.headers.get("x-api-token")
        return httpx.Response(
            201, json={"id": "rio-1", "paymentLink": "https://api.riopay.online/pay/x"}
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://api.riopay.online/pay/x"
    assert intent.provider_payment_id == "rio-1"
    assert captured["token"] == "rio-token"
    assert captured["body"]["externalId"] == "order-key-1"  # type: ignore[index,call-overload]


async def test_create_payment_raises_on_a_non_201_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": "bad amount"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(_order())


async def test_parse_webhook_completed_status_returns_result() -> None:
    result = await _gateway().parse_webhook(
        _signed_webhook({"id": "rio-1", "externalId": "order-key-1", "status": "COMPLETED"})
    )

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_defaults_the_webhook_secret_to_the_api_token() -> None:
    settings = {"api_token": "rio-token"}
    body = {"id": "rio-1", "externalId": "order-key-1", "status": "COMPLETED"}
    request = _signed_webhook(body, secret="rio-token")

    result = await _gateway(settings).parse_webhook(request)

    assert result is not None
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_invalid_signature_raises() -> None:
    body = json.dumps({"id": "rio-1", "externalId": "order-key-1", "status": "COMPLETED"}).encode()
    request = WebhookRequest(
        body=body, headers={"x-signature": "deadbeef"}, query={}, client_ip=None
    )
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_missing_signature_raises() -> None:
    body = json.dumps({"id": "rio-1", "externalId": "order-key-1", "status": "COMPLETED"}).encode()
    request = WebhookRequest(body=body, headers={}, query={}, client_ip=None)
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_non_completed_status_is_a_noop() -> None:
    result = await _gateway().parse_webhook(
        _signed_webhook({"id": "rio-1", "externalId": "order-key-1", "status": "PENDING"})
    )
    assert result is None
