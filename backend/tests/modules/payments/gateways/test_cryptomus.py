import base64
import hashlib
import json
from datetime import timedelta
from decimal import Decimal

import httpx
import orjson
import pytest

import app.modules.payments.gateways.cryptomus as cryptomus_module
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
from app.modules.payments.gateways.cryptomus import CryptomusGateway
from app.modules.payments.gateways.heleket import HeleketGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"merchant_id": "merchant-1", "api_key": "api-secret"}
_TRUSTED_IP = "91.227.144.54"
_WEBHOOK_URL = "https://shop.example/api/v1/payments/cryptomus"
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
        "gateway_type": PaymentGatewayType.CRYPTOMUS,
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


def _gateway() -> CryptomusGateway:
    return CryptomusGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(cryptomus_module, "http_client", httpx.AsyncClient(transport=handler))


def _sign(payload: dict[str, object], api_key: str = "api-secret") -> str:
    encoded = base64.b64encode(orjson.dumps(payload)).decode()
    return hashlib.md5(f"{encoded}{api_key}".encode()).hexdigest()


def _webhook(payload: dict[str, object], client_ip: str = _TRUSTED_IP) -> WebhookRequest:
    body = {**payload, "sign": _sign(payload)}
    return WebhookRequest(body=orjson.dumps(body), headers={}, query={}, client_ip=client_ip)


async def test_create_payment_signs_the_body_and_returns_the_payment_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["content"] = request.content
        captured["sign"] = request.headers.get("sign")
        captured["merchant"] = request.headers.get("merchant")
        return httpx.Response(
            200, json={"result": {"order_id": "order-key-1", "url": "https://pay.cryptomus.com/x"}}
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://pay.cryptomus.com/x"
    assert intent.provider_payment_id is None
    assert captured["merchant"] == "merchant-1"
    body = orjson.loads(captured["content"])  # type: ignore[arg-type]
    assert body["order_id"] == "order-key-1"
    assert body["currency"] == "USD"
    expected_sign = hashlib.md5(
        f"{base64.b64encode(captured['content']).decode()}api-secret".encode()  # type: ignore[arg-type]
    ).hexdigest()
    assert captured["sign"] == expected_sign


async def test_parse_webhook_valid_signature_paid_status_returns_result() -> None:
    result = await _gateway().parse_webhook(_webhook({"order_id": "order-key-1", "status": "paid"}))

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_paid_over_status_also_counts_as_paid() -> None:
    result = await _gateway().parse_webhook(
        _webhook({"order_id": "order-key-1", "status": "paid_over"})
    )
    assert result is not None
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_untrusted_ip_raises() -> None:
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(
            _webhook({"order_id": "order-key-1", "status": "paid"}, client_ip="1.2.3.4")
        )


async def test_parse_webhook_invalid_signature_raises() -> None:
    body = {"order_id": "order-key-1", "status": "paid", "sign": "0" * 32}
    request = WebhookRequest(body=orjson.dumps(body), headers={}, query={}, client_ip=_TRUSTED_IP)
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_matches_a_php_json_encode_style_signature() -> None:
    # Cryptomus signs its own PHP json_encode() output, which escapes non-ASCII
    # by default -- the payload here would sign differently if we re-serialized
    # it with orjson (which doesn't escape unicode) instead of matching that.
    payload = {"order_id": "order-key-1", "status": "paid", "note": "Оплата"}
    encoded = base64.b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode()
    ).decode()
    body = {**payload, "sign": hashlib.md5(f"{encoded}api-secret".encode()).hexdigest()}
    request = WebhookRequest(body=orjson.dumps(body), headers={}, query={}, client_ip=_TRUSTED_IP)

    result = await _gateway().parse_webhook(request)

    assert result is not None
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_confirm_check_is_a_noop() -> None:
    result = await _gateway().parse_webhook(
        _webhook({"order_id": "order-key-1", "status": "confirm_check"})
    )
    assert result is None


def test_heleket_reuses_cryptomus_with_its_own_base_and_networks() -> None:
    assert issubclass(HeleketGateway, CryptomusGateway)
    assert HeleketGateway.API_BASE == "https://api.heleket.com"
    assert HeleketGateway.trusted_networks != CryptomusGateway.trusted_networks
    assert HeleketGateway.currency is Currency.USD
