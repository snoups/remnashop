import hashlib
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

import httpx
import orjson
import pytest

import app.modules.payments.gateways.freekassa as freekassa_module
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
from app.modules.payments.gateways.freekassa import FreeKassaGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {
    "shop_id": "42",
    "api_key": "api-key-secret",
    "secret_word_2": "word2-secret",
    "payment_system_id": "4",
}
_TRUSTED_IP = "168.119.157.136"
_WEBHOOK_URL = "https://shop.example/api/v1/payments/freekassa"
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
        "gateway_type": PaymentGatewayType.FREEKASSA,
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


def _gateway() -> FreeKassaGateway:
    return FreeKassaGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(freekassa_module, "http_client", httpx.AsyncClient(transport=handler))


def _signed_webhook(**fields: str) -> bytes:
    raw = f"{fields['MERCHANT_ID']}:{fields['AMOUNT']}:word2-secret:{fields['MERCHANT_ORDER_ID']}"
    sign = hashlib.md5(raw.encode()).hexdigest()
    return urlencode({**fields, "SIGN": sign}).encode()


def _webhook(body: bytes, client_ip: str = _TRUSTED_IP) -> WebhookRequest:
    return WebhookRequest(body=body, headers={}, query={}, client_ip=client_ip)


async def test_create_payment_sends_a_signed_order_and_returns_the_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = orjson.loads(request.content)
        return httpx.Response(200, json={"type": "success", "location": "https://pay.fk.life/x"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://pay.fk.life/x"
    assert intent.provider_payment_id is None
    body = captured["body"]
    assert body["shopId"] == 42  # type: ignore[index,call-overload]
    assert body["paymentId"] == "order-key-1"  # type: ignore[index,call-overload]
    assert body["i"] == 4  # type: ignore[index,call-overload]
    assert body["amount"] == "500.00"  # type: ignore[index,call-overload]
    assert "signature" in body  # type: ignore[operator]


async def test_create_payment_raises_when_api_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"type": "error", "message": "bad request"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(_order())


async def test_parse_webhook_valid_signature_from_trusted_ip_returns_paid() -> None:
    body = _signed_webhook(MERCHANT_ID="42", AMOUNT="500.00", MERCHANT_ORDER_ID="order-key-1")

    result = await _gateway().parse_webhook(_webhook(body))

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_untrusted_ip_raises() -> None:
    body = _signed_webhook(MERCHANT_ID="42", AMOUNT="500.00", MERCHANT_ORDER_ID="order-key-1")

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(body, client_ip="1.2.3.4"))


async def test_parse_webhook_invalid_signature_raises() -> None:
    body = urlencode(
        {
            "MERCHANT_ID": "42",
            "AMOUNT": "500.00",
            "MERCHANT_ORDER_ID": "order-key-1",
            "SIGN": "0" * 32,
        }
    ).encode()

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(body))


async def test_webhook_ack_is_always_yes() -> None:
    body = _signed_webhook(MERCHANT_ID="42", AMOUNT="500.00", MERCHANT_ORDER_ID="order-key-1")
    gateway = _gateway()

    result = await gateway.parse_webhook(_webhook(body))

    assert gateway.webhook_ack(result) == "YES"
