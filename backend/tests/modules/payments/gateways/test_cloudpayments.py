import base64
import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

import httpx
import pytest

import app.modules.payments.gateways.cloudpayments as cloudpayments_module
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
from app.modules.payments.gateways.cloudpayments import CloudPaymentsGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"public_id": "pub-1", "api_secret": "cp-secret"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/cloudpayments"
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
        "gateway_type": PaymentGatewayType.CLOUDPAYMENTS,
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


def _gateway() -> CloudPaymentsGateway:
    return CloudPaymentsGateway(
        settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL
    )


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(cloudpayments_module, "_client", httpx.AsyncClient(transport=handler))


def _webhook(fields: dict[str, str], secret: str = "cp-secret") -> WebhookRequest:
    raw = urlencode(fields).encode()
    signature = base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest()).decode()
    return WebhookRequest(body=raw, headers={"content-hmac": signature}, query={}, client_ip=None)


async def test_create_payment_uses_basic_auth_and_returns_the_model_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "Success": True,
                "Model": {"Id": "cp-1", "Url": "https://cloudpayments.ru/pay/x"},
            },
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://cloudpayments.ru/pay/x"
    assert intent.provider_payment_id == "cp-1"
    expected_auth = "Basic " + base64.b64encode(b"pub-1:cp-secret").decode()
    assert captured["auth"] == expected_auth
    assert captured["body"]["InvoiceId"] == "order-key-1"  # type: ignore[index,call-overload]


async def test_create_payment_raises_when_api_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Success": False, "Message": "bad public id"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(_order())


async def test_parse_webhook_pay_notification_returns_result() -> None:
    fields = {
        "TransactionId": "123",
        "InvoiceId": "order-key-1",
        "Status": "Completed",
        "AuthCode": "A1B2C3",
    }

    result = await _gateway().parse_webhook(_webhook(fields))

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.provider_payment_id == "123"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_check_notification_is_a_noop() -> None:
    # No Reason/AuthCode -- CloudPayments' pre-auth Check notification.
    fields = {"TransactionId": "123", "InvoiceId": "order-key-1", "Status": "Completed"}

    result = await _gateway().parse_webhook(_webhook(fields))

    assert result is None


async def test_parse_webhook_declined_status_is_a_noop() -> None:
    fields = {"TransactionId": "123", "InvoiceId": "order-key-1", "Status": "Declined"}

    result = await _gateway().parse_webhook(_webhook(fields))

    assert result is None


async def test_parse_webhook_invalid_signature_raises() -> None:
    raw = urlencode({"TransactionId": "123", "Status": "Completed"}).encode()
    request = WebhookRequest(
        body=raw, headers={"content-hmac": "deadbeef"}, query={}, client_ip=None
    )
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_parse_webhook_missing_signature_raises() -> None:
    raw = urlencode({"TransactionId": "123", "Status": "Completed"}).encode()
    request = WebhookRequest(body=raw, headers={}, query={}, client_ip=None)
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(request)


async def test_webhook_ack_is_always_the_code_zero_json() -> None:
    fields = {"TransactionId": "123", "InvoiceId": "order-key-1", "Status": "Completed"}
    gateway = _gateway()

    result = await gateway.parse_webhook(_webhook(fields))

    assert gateway.webhook_ack(result) == '{"code": 0}'
