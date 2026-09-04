import hashlib
import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

import app.modules.payments.gateways.mulenpay as mulenpay_module
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
from app.modules.payments.gateways.mulenpay import MulenPayGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"api_key": "bearer-token", "secret_key": "sign-secret", "shop_id": "7"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/mulenpay"
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
        "gateway_type": PaymentGatewayType.MULENPAY,
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


def _gateway() -> MulenPayGateway:
    return MulenPayGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(mulenpay_module, "http_client", httpx.AsyncClient(transport=handler))


def _sign(currency: str, amount: str, shop_id: str, secret: str = "sign-secret") -> str:
    return hashlib.sha1(f"{currency}{amount}{shop_id}{secret}".encode()).hexdigest()


def _webhook(body: dict[str, object]) -> WebhookRequest:
    return WebhookRequest(body=json.dumps(body).encode(), headers={}, query={}, client_ip=None)


async def test_create_payment_sends_a_signed_payload_and_returns_the_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200, json={"success": True, "paymentUrl": "https://mulenpay.ru/pay/xyz"}
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://mulenpay.ru/pay/xyz"
    assert intent.provider_payment_id is None
    assert captured["auth"] == "Bearer bearer-token"
    body = captured["body"]
    assert body["uuid"] == "order-key-1"  # type: ignore[index,call-overload]
    assert body["shopId"] == 7  # type: ignore[index,call-overload]
    assert body["sign"] == _sign("rub", "500.00", "7")  # type: ignore[index,call-overload]


async def test_create_payment_raises_when_api_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": False})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(_order())


async def test_parse_webhook_valid_signature_returns_paid() -> None:
    body = {
        "uuid": "order-key-1",
        "payment_status": "success",
        "amount": "500.00",
        "currency": "rub",
        "sign": _sign("rub", "500.00", "7"),
    }

    result = await _gateway().parse_webhook(_webhook(body))

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_invalid_signature_raises() -> None:
    body = {
        "uuid": "order-key-1",
        "payment_status": "success",
        "amount": "500.00",
        "currency": "rub",
        "sign": "0" * 40,
    }

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(body))


async def test_parse_webhook_cancel_status_returns_none() -> None:
    body = {
        "uuid": "order-key-1",
        "payment_status": "cancel",
        "amount": "500.00",
        "currency": "rub",
        "sign": _sign("rub", "500.00", "7"),
    }

    result = await _gateway().parse_webhook(_webhook(body))

    assert result is None


async def test_parse_webhook_missing_uuid_raises() -> None:
    body = {"payment_status": "success", "sign": _sign("rub", "500.00", "7")}

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(body))
