import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

import app.modules.payments.gateways.platega as platega_module
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
from app.modules.payments.gateways.platega import PlategaGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"merchant_id": "merchant-1", "api_key": "secret-key"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/platega"
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
        "gateway_type": PaymentGatewayType.PLATEGA,
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


def _gateway(settings: dict[str, str] = _SETTINGS) -> PlategaGateway:
    return PlategaGateway(settings=settings, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(platega_module, "http_client", httpx.AsyncClient(transport=handler))


def _webhook(body: dict[str, object], headers: dict[str, str]) -> WebhookRequest:
    return WebhookRequest(body=json.dumps(body).encode(), headers=headers, query={}, client_ip=None)


async def test_create_payment_uses_the_multi_method_endpoint_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"transactionId": "txn-1", "redirect": "https://app.platega.io/pay/1"}
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://app.platega.io/pay/1"
    assert intent.provider_payment_id == "txn-1"
    assert captured["path"] == "/v2/transaction/process"
    headers = captured["headers"]
    assert headers["X-MerchantId"] == "merchant-1"  # type: ignore[index]
    assert headers["X-Secret"] == "secret-key"  # type: ignore[index]
    assert "paymentMethod" not in captured["body"]  # type: ignore[operator]


async def test_create_payment_uses_the_single_method_endpoint_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"transactionId": "txn-1", "url": "https://pay/1"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    await _gateway({**_SETTINGS, "payment_method": "7"}).create_payment(_order())

    assert captured["path"] == "/transaction/process"
    assert captured["body"]["paymentMethod"] == 7  # type: ignore[index,call-overload]


async def test_parse_webhook_valid_credentials_returns_paid() -> None:
    body = {"id": "txn-1", "status": "CONFIRMED"}
    headers = {"x-merchantid": "merchant-1", "x-secret": "secret-key"}

    result = await _gateway().parse_webhook(_webhook(body, headers))

    assert result is not None
    assert result.reference == ""
    assert result.provider_payment_id == "txn-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_wrong_secret_raises() -> None:
    body = {"id": "txn-1", "status": "CONFIRMED"}
    headers = {"x-merchantid": "merchant-1", "x-secret": "wrong"}

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(body, headers))


async def test_parse_webhook_missing_headers_raises() -> None:
    body = {"id": "txn-1", "status": "CONFIRMED"}

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(body, {}))


async def test_parse_webhook_non_confirmed_status_returns_none() -> None:
    body = {"id": "txn-1", "status": "CANCELED"}
    headers = {"x-merchantid": "merchant-1", "x-secret": "secret-key"}

    result = await _gateway().parse_webhook(_webhook(body, headers))

    assert result is None
