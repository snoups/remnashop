import hashlib
import hmac
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

import httpx
import orjson
import pytest

import app.modules.payments.gateways.kassa_ai as kassa_ai_module
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
from app.modules.payments.gateways.kassa_ai import KassaAIGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"shop_id": "77", "api_key": "kai-api-key", "secret_word_2": "kai-secret-2"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/kassaai"
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
        "gateway_type": PaymentGatewayType.KASSAAI,
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


def _gateway() -> KassaAIGateway:
    return KassaAIGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(kassa_ai_module, "_client", httpx.AsyncClient(transport=handler))


def _webhook(fields: dict[str, str]) -> WebhookRequest:
    raw = urlencode(fields).encode()
    return WebhookRequest(body=raw, headers={}, query={}, client_ip=None)


def _sign(shop_id: str, amount: str, order_id: str, secret2: str = "kai-secret-2") -> str:
    raw = f"{shop_id}:{amount}:{secret2}:{order_id}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


async def test_create_payment_signs_the_sorted_pipe_joined_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = orjson.loads(request.content)
        return httpx.Response(
            200,
            json={"type": "success", "location": "https://fk.life/pay/x", "orderId": "kai-1"},
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://fk.life/pay/x"
    assert intent.provider_payment_id is None
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["paymentId"] == "order-key-1"
    assert body["shopId"] == 77
    assert body["i"] == 44
    signed = {key: value for key, value in body.items() if key != "signature"}
    expected_msg = "|".join(str(signed[key]) for key in sorted(signed.keys()))
    expected_signature = hmac.new(
        b"kai-api-key", expected_msg.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert body["signature"] == expected_signature


async def test_create_payment_raises_on_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"type": "error", "error": "bad shop"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(_order())


async def test_parse_webhook_valid_signature_returns_paid_result() -> None:
    fields = {
        "MERCHANT_ID": "77",
        "AMOUNT": "500.00",
        "MERCHANT_ORDER_ID": "order-key-1",
        "intid": "kai-tx-1",
        "CUR_ID": "44",
    }
    fields["SIGN"] = _sign("77", "500.00", "order-key-1")

    result = await _gateway().parse_webhook(_webhook(fields))

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.provider_payment_id == "kai-tx-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_invalid_signature_raises() -> None:
    fields = {
        "MERCHANT_ID": "77",
        "AMOUNT": "500.00",
        "MERCHANT_ORDER_ID": "order-key-1",
        "intid": "kai-tx-1",
        "SIGN": "deadbeef",
    }

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(fields))


async def test_parse_webhook_wrong_merchant_id_raises() -> None:
    fields = {
        "MERCHANT_ID": "999",
        "AMOUNT": "500.00",
        "MERCHANT_ORDER_ID": "order-key-1",
        "intid": "kai-tx-1",
    }
    fields["SIGN"] = _sign("999", "500.00", "order-key-1")

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(fields))


async def test_webhook_ack_is_yes() -> None:
    fields = {
        "MERCHANT_ID": "77",
        "AMOUNT": "500.00",
        "MERCHANT_ORDER_ID": "order-key-1",
        "intid": "kai-tx-1",
    }
    fields["SIGN"] = _sign("77", "500.00", "order-key-1")
    gateway = _gateway()

    result = await gateway.parse_webhook(_webhook(fields))

    assert gateway.webhook_ack(result) == "YES"
