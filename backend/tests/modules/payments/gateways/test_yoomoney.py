import hashlib
import hmac
from datetime import timedelta
from decimal import Decimal
from urllib.parse import parse_qs, quote, urlencode

import httpx
import pytest

import app.modules.payments.gateways.yoomoney as yoomoney_module
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
from app.modules.payments.gateways.yoomoney import YooMoneyGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"wallet_id": "410011234567890", "secret_key": "test-secret"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/yoomoney"
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
        "gateway_type": PaymentGatewayType.YOOMONEY,
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


def _gateway(settings: dict[str, str] = _SETTINGS) -> YooMoneyGateway:
    return YooMoneyGateway(settings=settings, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(yoomoney_module, "http_client", httpx.AsyncClient(transport=handler))


def _signed_body(secret: str, **fields: str) -> bytes:
    sign_str = "&".join(f"{key}={quote(value, safe='')}" for key, value in sorted(fields.items()))
    sign = hmac.new(secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode({**fields, "sign": sign}).encode("utf-8")


def _webhook(body: bytes) -> WebhookRequest:
    return WebhookRequest(body=body, headers={}, query={}, client_ip=None)


async def test_create_payment_posts_form_data_and_follows_the_redirect_to_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                302,
                headers={
                    "Location": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=abc"
                },
            )
        return httpx.Response(200)

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert (
        intent.confirmation_url == "https://yoomoney.ru/checkout/payments/v2/contract?orderId=abc"
    )
    assert intent.provider_payment_id is None
    first_request = requests[0]
    assert first_request.headers["content-type"] == "application/x-www-form-urlencoded"
    form = {k: v[0] for k, v in parse_qs(first_request.content.decode()).items()}
    assert form["receiver"] == "410011234567890"
    assert form["label"] == "order-key-1"
    assert form["sum"] == "500.00"
    assert form["successURL"] == _RETURN_URL


async def test_parse_webhook_valid_signature_returns_paid_result() -> None:
    body = _signed_body(
        "test-secret",
        label="order-key-1",
        operation_id="op-1",
        amount="500.00",
        withdraw_amount="500.00",
        currency="643",
        datetime="2026-09-02T12:00:00Z",
        sender="",
        codepro="false",
        notification_type="p2p-incoming",
    )

    result = await _gateway().parse_webhook(_webhook(body))

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID
    assert result.provider_payment_id == "op-1"


async def test_parse_webhook_invalid_signature_raises() -> None:
    body = urlencode({"label": "order-key-1", "sign": "not-the-real-signature"}).encode()

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(body))


async def test_parse_webhook_missing_signature_raises() -> None:
    body = urlencode({"label": "order-key-1"}).encode()

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(body))


async def test_parse_webhook_test_notification_is_a_noop() -> None:
    # YooMoney's dashboard "test" button sends operation_id=test-notification
    # unsigned -- not a real payment, never a verification failure.
    body = urlencode({"operation_id": "test-notification", "label": "order-key-1"}).encode()

    result = await _gateway().parse_webhook(_webhook(body))

    assert result is None


async def test_parse_webhook_missing_label_raises() -> None:
    body = _signed_body("test-secret", operation_id="op-1")

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(body))
