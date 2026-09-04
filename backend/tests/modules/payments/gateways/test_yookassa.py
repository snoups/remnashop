import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

import app.modules.payments.gateways.yookassa as yookassa_module
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
from app.modules.payments.gateways.base import WebhookRequest, WebhookResult
from app.modules.payments.gateways.yookassa import YooKassaGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"shop_id": "1000", "api_key": "test_key"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/yookassa"
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
        "gateway_type": PaymentGatewayType.YOOKASSA,
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


def _gateway() -> YooKassaGateway:
    return YooKassaGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(yookassa_module, "http_client", httpx.AsyncClient(transport=handler))


async def test_create_payment_sends_idempotence_key_ref_metadata_and_return_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "yk-payment-1",
                "confirmation": {"confirmation_url": "https://yookassa.ru/pay/1"},
            },
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.provider_payment_id == "yk-payment-1"
    assert intent.confirmation_url == "https://yookassa.ru/pay/1"
    request = captured["request"]
    assert request.headers["Idempotence-Key"] == "order-key-1"  # type: ignore[union-attr]
    body = captured["body"]
    assert body["metadata"]["order_ref"] == "order-key-1"  # type: ignore[index,call-overload]
    assert body["confirmation"]["return_url"] == _RETURN_URL  # type: ignore[index,call-overload]


async def _create_payment_body(
    monkeypatch: pytest.MonkeyPatch, order: PaymentOrderDto, settings: dict[str, str]
) -> dict[str, object]:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "yk-payment-1",
                "confirmation": {"confirmation_url": "https://yookassa.ru/pay/1"},
            },
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))
    gateway = YooKassaGateway(settings=settings, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)
    await gateway.create_payment(order)
    return captured["body"]  # type: ignore[return-value]


async def test_receipt_is_sent_when_both_email_and_vat_code_are_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = await _create_payment_body(
        monkeypatch,
        _order(customer_email="buyer@example.com"),
        {**_SETTINGS, "vat_code": "1"},
    )
    receipt = body["receipt"]
    assert receipt["customer"]["email"] == "buyer@example.com"  # type: ignore[index,call-overload]
    assert receipt["items"][0]["vat_code"] == 1  # type: ignore[index,call-overload]


async def test_no_receipt_when_vat_code_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    body = await _create_payment_body(
        monkeypatch, _order(customer_email="buyer@example.com"), _SETTINGS
    )
    assert "receipt" not in body


async def test_no_receipt_when_customer_email_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    body = await _create_payment_body(monkeypatch, _order(), {**_SETTINGS, "vat_code": "1"})
    assert "receipt" not in body


def _webhook(body: dict[str, object]) -> WebhookRequest:
    return WebhookRequest(
        body=json.dumps(body).encode(), headers={}, query={}, client_ip="185.71.76.1"
    )


async def test_parse_webhook_extracts_ref_and_status_from_metadata() -> None:
    result = await _gateway().parse_webhook(
        _webhook(
            {
                "event": "payment.succeeded",
                "object": {
                    "id": "yk-payment-1",
                    "status": "succeeded",
                    "metadata": {"order_ref": "order-key-1"},
                },
            }
        )
    )
    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID
    assert result.provider_payment_id == "yk-payment-1"


async def test_parse_webhook_falls_back_to_empty_ref_without_metadata() -> None:
    result = await _gateway().parse_webhook(
        _webhook({"object": {"id": "yk-payment-2", "status": "succeeded"}})
    )
    assert result is not None
    assert result.reference == ""
    assert result.provider_payment_id == "yk-payment-2"


async def test_parse_webhook_returns_none_for_non_terminal_status() -> None:
    result = await _gateway().parse_webhook(
        _webhook({"object": {"id": "x", "status": "waiting_for_capture"}})
    )
    assert result is None


async def test_parse_webhook_raises_on_malformed_body() -> None:
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(
            WebhookRequest(body=b"not-json", headers={}, query={}, client_ip=None)
        )


async def test_parse_webhook_raises_when_object_is_not_a_dict() -> None:
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook({"object": None}))


async def test_verify_payment_true_only_on_succeeded_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/payments/yk-payment-1")
        return httpx.Response(200, json={"id": "yk-payment-1", "status": "succeeded"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))
    result = WebhookResult(reference="", status=PaymentOrderStatus.PAID)
    assert (
        await _gateway().verify_payment(_order(external_payment_id="yk-payment-1"), result) is True
    )


async def test_verify_payment_false_on_pending_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "yk-payment-1", "status": "pending"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))
    result = WebhookResult(reference="", status=PaymentOrderStatus.PAID)
    assert (
        await _gateway().verify_payment(_order(external_payment_id="yk-payment-1"), result) is False
    )
