import hashlib
import hmac
from datetime import timedelta
from decimal import Decimal

import httpx
import orjson
import pytest

import app.modules.payments.gateways.donut as donut_module
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
from app.modules.payments.gateways.donut import DonutGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"token": "dnt-token", "secret": "dnt-secret"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/donut"
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
        "gateway_type": PaymentGatewayType.DONUT,
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


def _gateway() -> DonutGateway:
    return DonutGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(donut_module, "http_client", httpx.AsyncClient(transport=handler))


def _sign(parts: list[tuple[str, object]], secret: str = "dnt-secret") -> str:
    chunks = [f"{key}={value}" for key, value in parts if value not in (None, "")]
    return hmac.new(secret.encode(), "".join(chunks).encode(), hashlib.sha256).hexdigest()


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


async def test_create_payment_supports_redirect_and_returns_the_redirect_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = orjson.loads(request.content)
        return httpx.Response(
            200,
            json={
                "status": {"type": "success"},
                "transaction_id": "dnt-1",
                "redirect_url": "https://gw.donut.business/pay/x",
            },
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://gw.donut.business/pay/x"
    assert intent.provider_payment_id == "dnt-1"
    body = captured["body"]
    assert body["redirect"] == "true"  # type: ignore[index,call-overload]
    assert body["return_url"] == _RETURN_URL  # type: ignore[index,call-overload]


async def test_create_payment_falls_back_to_the_return_url_when_no_redirect_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": {"type": "created"}, "transaction_id": "dnt-1"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == _RETURN_URL


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
        "token": "dnt-token",
        "transaction_id": "dnt-1",
        "order_id": "order-key-1",
        "amount": {"value": "500.00", "currency": "RUB"},
        "status": {"type": "success"},
    }
    payload["signature"] = _callback_signature(payload)

    result = await _gateway().parse_webhook(_webhook(payload))

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_invalid_signature_raises() -> None:
    payload = {
        "token": "dnt-token",
        "transaction_id": "dnt-1",
        "order_id": "order-key-1",
        "amount": {"value": "500.00", "currency": "RUB"},
        "status": {"type": "success"},
        "signature": "deadbeef",
    }
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(payload))


async def test_verify_payment_accepts_full_amount() -> None:
    payload: dict[str, object] = {
        "token": "dnt-token",
        "transaction_id": "dnt-1",
        "order_id": "order-key-1",
        "amount": {"value": "500.00", "currency": "RUB"},
        "status": {"type": "success"},
    }
    payload["signature"] = _callback_signature(payload)
    gateway = _gateway()
    result = await gateway.parse_webhook(_webhook(payload))

    assert result is not None
    assert await gateway.verify_payment(_order(), result) is True


async def test_verify_payment_rejects_an_underpayment() -> None:
    payload: dict[str, object] = {
        "token": "dnt-token",
        "transaction_id": "dnt-1",
        "order_id": "order-key-1",
        "amount": {"value": "499.99", "currency": "RUB"},
        "status": {"type": "success"},
    }
    payload["signature"] = _callback_signature(payload)
    gateway = _gateway()
    result = await gateway.parse_webhook(_webhook(payload))

    assert result is not None
    assert await gateway.verify_payment(_order(), result) is False


async def test_verify_payment_rejects_a_recalculated_transfer() -> None:
    payload: dict[str, object] = {
        "token": "dnt-token",
        "transaction_id": "dnt-1",
        "order_id": "order-key-1",
        "amount": {"value": "500.00", "currency": "RUB"},
        "recalculated": True,
        "status": {"type": "success"},
    }
    payload["signature"] = _callback_signature(payload)
    gateway = _gateway()
    result = await gateway.parse_webhook(_webhook(payload))

    assert result is not None
    assert await gateway.verify_payment(_order(), result) is False


async def test_parse_webhook_pending_status_is_a_noop() -> None:
    payload: dict[str, object] = {
        "token": "dnt-token",
        "transaction_id": "dnt-1",
        "order_id": "order-key-1",
        "amount": {"value": "500.00", "currency": "RUB"},
        "status": {"type": "created"},
    }
    payload["signature"] = _callback_signature(payload)

    result = await _gateway().parse_webhook(_webhook(payload))

    assert result is None
