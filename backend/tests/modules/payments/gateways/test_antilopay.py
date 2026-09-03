import base64
import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import app.modules.payments.gateways.antilopay as antilopay_module
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
from app.modules.payments.gateways.antilopay import AntilopayGateway
from app.modules.payments.gateways.base import WebhookRequest
from tests.modules.subscriptions.factories import make_plan_snapshot

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()


def _b64_der_private() -> str:
    der = _PRIVATE_KEY.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.b64encode(der).decode()


def _b64_der_public() -> str:
    der = _PUBLIC_KEY.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return base64.b64encode(der).decode()


_SETTINGS = {
    "secret_id": "secret-1",
    "private_key": _b64_der_private(),
    "public_key": _b64_der_public(),
    "project_id": "project-1",
}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/antilopay"
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
        "gateway_type": PaymentGatewayType.ANTILOPAY,
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


def _gateway() -> AntilopayGateway:
    return AntilopayGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(antilopay_module, "_client", httpx.AsyncClient(transport=handler))


def _sign(raw_body: bytes) -> str:
    signature = _PRIVATE_KEY.sign(raw_body, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode()


def _signed_webhook(body: dict[str, object]) -> WebhookRequest:
    raw = json.dumps(body).encode()
    return WebhookRequest(
        body=raw, headers={"x-apay-callback": _sign(raw)}, query={}, client_ip=None
    )


async def test_create_payment_signs_the_body_and_returns_the_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["secret_id"] = request.headers.get("x-apay-secret-id")
        captured["sign"] = request.headers.get("x-apay-sign")
        return httpx.Response(
            200,
            json={
                "code": 0,
                "payment_id": "alp-1",
                "payment_url": "https://lk.antilopay.com/pay/x",
            },
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://lk.antilopay.com/pay/x"
    assert intent.provider_payment_id == "alp-1"
    assert captured["secret_id"] == "secret-1"
    assert captured["sign"]
    body = captured["body"]
    assert body["order_id"] == "order-key-1"  # type: ignore[index,call-overload]
    assert body["project_identificator"] == "project-1"  # type: ignore[index,call-overload]


async def test_create_payment_raises_on_a_nonzero_api_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 1, "message": "bad project"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(_order())


async def test_parse_webhook_success_status_returns_result() -> None:
    result = await _gateway().parse_webhook(
        _signed_webhook({"type": "payment", "order_id": "order-key-1", "status": "SUCCESS"})
    )

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_invalid_signature_raises() -> None:
    body = json.dumps({"type": "payment", "order_id": "order-key-1", "status": "SUCCESS"}).encode()
    request = WebhookRequest(
        body=body,
        headers={"x-apay-callback": base64.b64encode(b"garbage").decode()},
        query={},
        client_ip=None,
    )
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_missing_signature_raises() -> None:
    body = json.dumps({"order_id": "order-key-1", "status": "SUCCESS"}).encode()
    request = WebhookRequest(body=body, headers={}, query={}, client_ip=None)
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_non_payment_type_is_a_noop() -> None:
    result = await _gateway().parse_webhook(
        _signed_webhook({"type": "refund", "order_id": "order-key-1", "status": "SUCCESS"})
    )
    assert result is None


async def test_parse_webhook_pending_status_is_a_noop() -> None:
    result = await _gateway().parse_webhook(
        _signed_webhook({"type": "payment", "order_id": "order-key-1", "status": "PENDING"})
    )
    assert result is None
