import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

import app.modules.payments.gateways.cryptopay as cryptopay_module
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
from app.modules.payments.gateways.cryptopay import CryptoPayGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"api_key": "cryptopay-token"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/cryptopay"
_RETURN_URL = "https://shop.example"


def _order(**overrides: object) -> PaymentOrderDto:
    defaults: dict[str, object] = {
        "id": 1,
        "user_id": 1,
        "plan_id": 1,
        "plan_snapshot": make_plan_snapshot(plan_id=1),
        "duration_days": 30,
        "currency": Currency.USD,
        "purchase_type": PurchaseType.NEW,
        "gateway_type": PaymentGatewayType.CRYPTOPAY,
        "status": PaymentOrderStatus.PENDING,
        "base_price": Decimal("10"),
        "discount_percent": 0,
        "discount_source": DiscountSource.NONE,
        "final_price": Decimal("10"),
        "idempotency_key": "order-key-1",
        "expires_at": datetime_now() + timedelta(minutes=30),
    }
    defaults.update(overrides)
    return PaymentOrderDto(**defaults)  # type: ignore[arg-type]


def _gateway() -> CryptoPayGateway:
    return CryptoPayGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(cryptopay_module, "_client", httpx.AsyncClient(transport=handler))


def _signed_webhook(body: dict[str, object], token: str = "cryptopay-token") -> WebhookRequest:
    raw = json.dumps(body).encode()
    secret = hashlib.sha256(token.encode()).digest()
    signature = hmac.new(secret, raw, hashlib.sha256).hexdigest()
    return WebhookRequest(
        body=raw, headers={"crypto-pay-api-signature": signature}, query={}, client_ip=None
    )


async def test_create_payment_sends_the_token_header_and_order_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["token"] = request.headers.get("crypto-pay-api-token")
        return httpx.Response(
            200,
            json={"ok": True, "result": {"bot_invoice_url": "https://t.me/CryptoBot?start=x"}},
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://t.me/CryptoBot?start=x"
    assert intent.provider_payment_id is None
    assert captured["token"] == "cryptopay-token"
    body = captured["body"]
    assert body["payload"] == "order-key-1"  # type: ignore[index,call-overload]
    assert body["fiat"] == "USD"  # type: ignore[index,call-overload]


async def test_create_payment_raises_when_api_not_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "error": {"code": 400}})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(_order())


async def test_parse_webhook_invoice_paid_returns_result() -> None:
    result = await _gateway().parse_webhook(
        _signed_webhook(
            {
                "update_type": "invoice_paid",
                "payload": {"payload": "order-key-1", "status": "paid"},
            }
        )
    )

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_bad_signature_raises() -> None:
    request = WebhookRequest(
        body=json.dumps({"update_type": "invoice_paid"}).encode(),
        headers={"crypto-pay-api-signature": "0" * 64},
        query={},
        client_ip=None,
    )
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_missing_signature_raises() -> None:
    request = WebhookRequest(
        body=json.dumps({"update_type": "invoice_paid"}).encode(),
        headers={},
        query={},
        client_ip=None,
    )
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_non_paid_update_type_is_a_noop() -> None:
    result = await _gateway().parse_webhook(
        _signed_webhook({"update_type": "invoice_expired", "payload": {}})
    )
    assert result is None
