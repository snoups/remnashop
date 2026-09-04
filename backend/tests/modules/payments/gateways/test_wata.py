import base64
import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import app.modules.payments.gateways.wata as wata_module
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
from app.modules.payments.gateways.wata import WataGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"api_key": "wata-token"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/wata"
_RETURN_URL = "https://shop.example"

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_PEM = (
    _PRIVATE_KEY.public_key()
    .public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)


def _order(**overrides: object) -> PaymentOrderDto:
    defaults: dict[str, object] = {
        "id": 1,
        "user_id": 1,
        "plan_id": 1,
        "plan_snapshot": make_plan_snapshot(plan_id=1),
        "duration_days": 30,
        "currency": Currency.USD,
        "purchase_type": PurchaseType.NEW,
        "gateway_type": PaymentGatewayType.WATA,
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


def _gateway() -> WataGateway:
    return WataGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(wata_module, "http_client", httpx.AsyncClient(transport=handler))


def _sign(raw: bytes) -> str:
    signature = _PRIVATE_KEY.sign(raw, padding.PKCS1v15(), hashes.SHA512())
    return base64.b64encode(signature).decode()


def _public_key_response() -> httpx.Response:
    return httpx.Response(200, json={"value": _PUBLIC_PEM})


async def test_create_payment_sends_bearer_and_returns_the_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"url": "https://wata.pro/pay/x"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://wata.pro/pay/x"
    assert captured["auth"] == "Bearer wata-token"
    body = captured["body"]
    assert body["orderId"] == "order-key-1"  # type: ignore[index,call-overload]
    assert body["type"] == "OneTime"  # type: ignore[index,call-overload]


async def test_parse_webhook_verifies_rsa_signature_against_fetched_public_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = json.dumps({"orderId": "order-key-1", "transactionStatus": "Paid"}).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/public-key")
        return _public_key_response()

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    result = await _gateway().parse_webhook(
        WebhookRequest(body=raw, headers={"x-signature": _sign(raw)}, query={}, client_ip=None)
    )

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_bad_signature_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = json.dumps({"orderId": "order-key-1", "transactionStatus": "Paid"}).encode()

    _patch_transport(monkeypatch, httpx.MockTransport(lambda request: _public_key_response()))

    tampered_sig = _sign(b"a different body")
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(
            WebhookRequest(
                body=raw, headers={"x-signature": tampered_sig}, query={}, client_ip=None
            )
        )


async def test_parse_webhook_missing_signature_raises() -> None:
    raw = json.dumps({"orderId": "order-key-1", "transactionStatus": "Paid"}).encode()
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(
            WebhookRequest(body=raw, headers={}, query={}, client_ip=None)
        )


async def test_parse_webhook_declined_status_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = json.dumps({"orderId": "order-key-1", "transactionStatus": "Declined"}).encode()
    _patch_transport(monkeypatch, httpx.MockTransport(lambda request: _public_key_response()))

    result = await _gateway().parse_webhook(
        WebhookRequest(body=raw, headers={"x-signature": _sign(raw)}, query={}, client_ip=None)
    )
    assert result is None
