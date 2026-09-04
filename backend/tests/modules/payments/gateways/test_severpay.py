import hashlib
import hmac
from datetime import timedelta
from decimal import Decimal

import httpx
import orjson
import pytest

import app.modules.payments.gateways.severpay as severpay_module
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
from app.modules.payments.gateways.severpay import SeverPayGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"mid": "42", "token": "sp-token"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/severpay"
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
        "gateway_type": PaymentGatewayType.SEVERPAY,
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


def _gateway() -> SeverPayGateway:
    return SeverPayGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(severpay_module, "http_client", httpx.AsyncClient(transport=handler))


def _sign(body: dict[str, object], token: str = "sp-token") -> str:
    sorted_body = dict(sorted(body.items()))
    return hmac.new(token.encode(), orjson.dumps(sorted_body), hashlib.sha256).hexdigest()


def _webhook_body(data: dict[str, object], webhook_type: str = "payin") -> dict[str, object]:
    body: dict[str, object] = {"type": webhook_type, "data": data}
    body["sign"] = _sign(body)
    return body


def _webhook(body: dict[str, object]) -> WebhookRequest:
    return WebhookRequest(body=orjson.dumps(body), headers={}, query={}, client_ip=None)


async def test_create_payment_signs_the_body_and_returns_the_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = orjson.loads(request.content)
        return httpx.Response(
            200, json={"status": True, "data": {"id": "sp-1", "url": "https://severpay.io/pay/x"}}
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://severpay.io/pay/x"
    assert intent.provider_payment_id == "sp-1"
    body = captured["body"]
    assert body["order_id"] == "order-key-1"  # type: ignore[index,call-overload]
    assert body["mid"] == 42  # type: ignore[index,call-overload]
    assert "sign" in body  # type: ignore[operator]
    assert "salt" in body  # type: ignore[operator]


async def test_create_payment_raises_when_api_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": False, "msg": "bad mid"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(_order())


async def test_parse_webhook_success_status_returns_result() -> None:
    body = _webhook_body({"id": "sp-1", "order_id": "order-key-1", "status": "success"})

    result = await _gateway().parse_webhook(_webhook(body))

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_invalid_signature_raises() -> None:
    body = {
        "type": "payin",
        "data": {"id": "sp-1", "order_id": "order-key-1", "status": "success"},
        "sign": "deadbeef",
    }
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(body))


async def test_parse_webhook_missing_signature_raises() -> None:
    body = {"type": "payin", "data": {"id": "sp-1", "status": "success"}}
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(body))


async def test_parse_webhook_non_payin_type_is_a_noop() -> None:
    body = _webhook_body(
        {"id": "sp-1", "order_id": "order-key-1", "status": "success"}, webhook_type="payout"
    )

    result = await _gateway().parse_webhook(_webhook(body))

    assert result is None


async def test_parse_webhook_non_success_status_is_a_noop() -> None:
    body = _webhook_body({"id": "sp-1", "order_id": "order-key-1", "status": "new"})

    result = await _gateway().parse_webhook(_webhook(body))

    assert result is None
