import hashlib
import hmac
from datetime import timedelta
from decimal import Decimal

import httpx
import orjson
import pytest

import app.modules.payments.gateways.jupiter as jupiter_module
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
from app.modules.payments.gateways.jupiter import JupiterGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"token": "jup-token", "secret": "jup-secret"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/jupiter"
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
        "gateway_type": PaymentGatewayType.JUPITER,
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


def _gateway() -> JupiterGateway:
    return JupiterGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(jupiter_module, "_client", httpx.AsyncClient(transport=handler))


def _sign(parts: list[tuple[str, object]], secret: str = "jup-secret") -> str:
    chunks = []
    for key, value in parts:
        if value is None or value == "":
            continue
        chunks.append(f"{key}={value}")
    message = "".join(chunks)
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def _callback_signature(payload: dict[str, object]) -> str:
    amount = payload.get("amount") or {}
    status = payload.get("status") or {}
    return _sign(
        [
            ("token", payload.get("token")),
            ("transaction_id", payload.get("transaction_id")),
            ("order_id", payload.get("order_id")),
            ("amount.value", amount.get("value")),  # type: ignore[union-attr]
            ("amount.currency", amount.get("currency")),  # type: ignore[union-attr]
            ("recalculated", payload.get("recalculated")),
            ("status.type", status.get("type")),  # type: ignore[union-attr]
        ]
    )


def _webhook(payload: dict[str, object]) -> WebhookRequest:
    return WebhookRequest(body=orjson.dumps(payload), headers={}, query={}, client_ip=None)


async def test_create_payment_signs_the_fixed_fields_and_returns_the_qr_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = orjson.loads(request.content)
        return httpx.Response(
            200,
            json={
                "status": {"type": "processing"},
                "transaction_id": "jup-1",
                "details": {"qrcode_url": "https://app.juppiter.tech/qr/x"},
            },
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://app.juppiter.tech/qr/x"
    assert intent.provider_payment_id == "jup-1"
    body = captured["body"]
    assert body["order_id"] == "order-key-1"  # type: ignore[index,call-overload]
    expected_sig = _sign(
        [
            ("token", body["token"]),  # type: ignore[index,call-overload]
            ("order_id", body["order_id"]),  # type: ignore[index,call-overload]
            ("amount.value", body["amount"]["value"]),  # type: ignore[index,call-overload]
            ("amount.currency", body["amount"]["currency"]),  # type: ignore[index,call-overload]
            ("customer.id", body["customer"]["id"]),  # type: ignore[index,call-overload]
            ("redirect", body["redirect"]),  # type: ignore[index,call-overload]
        ]
    )
    assert body["signature"] == expected_sig  # type: ignore[index,call-overload]


async def test_create_payment_raises_on_an_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": {"type": "error", "error_description": "bad token"}}
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(_order())


async def test_parse_webhook_success_status_returns_result() -> None:
    payload: dict[str, object] = {
        "token": "jup-token",
        "transaction_id": "jup-1",
        "order_id": "order-key-1",
        "amount": {"value": "500.00", "currency": "RUB"},
        "status": {"type": "success"},
    }
    payload["signature"] = _callback_signature(payload)

    result = await _gateway().parse_webhook(_webhook(payload))

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.provider_payment_id == "jup-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_invalid_signature_raises() -> None:
    payload = {
        "token": "jup-token",
        "transaction_id": "jup-1",
        "order_id": "order-key-1",
        "amount": {"value": "500.00", "currency": "RUB"},
        "status": {"type": "success"},
        "signature": "deadbeef",
    }
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(payload))


async def test_parse_webhook_missing_signature_raises() -> None:
    payload = {"transaction_id": "jup-1", "status": {"type": "success"}}
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(payload))


async def test_parse_webhook_processing_status_is_a_noop() -> None:
    payload: dict[str, object] = {
        "token": "jup-token",
        "transaction_id": "jup-1",
        "order_id": "order-key-1",
        "amount": {"value": "500.00", "currency": "RUB"},
        "status": {"type": "processing"},
    }
    payload["signature"] = _callback_signature(payload)

    result = await _gateway().parse_webhook(_webhook(payload))

    assert result is None
