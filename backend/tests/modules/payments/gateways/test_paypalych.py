import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

import httpx
import pytest

import app.modules.payments.gateways.paypalych as paypalych_module
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
from app.modules.payments.gateways.paypalych import PaypalychGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {
    "api_token": "pal-token",
    "shop_id": "shop-1",
    "signature_token": "pal-sig-token",
}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/paypalych"
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
        "gateway_type": PaymentGatewayType.PAYPALYCH,
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


def _gateway() -> PaypalychGateway:
    return PaypalychGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(paypalych_module, "http_client", httpx.AsyncClient(transport=handler))


def _sign(out_sum: str, inv_id: str, token: str = "pal-sig-token") -> str:
    return hashlib.md5(f"{out_sum}:{inv_id}:{token}".encode()).hexdigest().upper()


def _webhook_form(fields: dict[str, str]) -> WebhookRequest:
    raw = urlencode(fields).encode()
    return WebhookRequest(
        body=raw,
        headers={"content-type": "application/x-www-form-urlencoded"},
        query={},
        client_ip=None,
    )


async def test_create_payment_sends_bearer_auth_and_returns_transfer_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "success": True,
                "bill_id": "bill-1",
                "transfer_url": "https://pal24.pro/pay/x",
                "link_page_url": "https://pal24.pro/page/x",
            },
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://pal24.pro/pay/x"
    assert intent.provider_payment_id == "bill-1"
    assert captured["auth"] == "Bearer pal-token"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["order_id"] == "order-key-1"
    assert body["shop_id"] == "shop-1"
    assert body["type"] == "normal"


async def test_create_payment_falls_back_to_link_page_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "bill_id": "bill-1",
                "link_page_url": "https://pal24.pro/page/x",
            },
        )

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    intent = await _gateway().create_payment(_order())

    assert intent.confirmation_url == "https://pal24.pro/page/x"


async def test_create_payment_raises_when_api_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": False, "message": "bad shop_id"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(_order())


async def test_parse_webhook_success_status_returns_paid_result() -> None:
    fields = {
        "InvId": "order-key-1",
        "OutSum": "500.00",
        "Status": "SUCCESS",
        "TrsId": "trs-1",
    }
    fields["SignatureValue"] = _sign("500.00", "order-key-1")

    result = await _gateway().parse_webhook(_webhook_form(fields))

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.provider_payment_id == "trs-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_accepts_json_body() -> None:
    fields = {
        "InvId": "order-key-1",
        "OutSum": "500.00",
        "Status": "OVERPAID",
        "TrsId": "trs-1",
    }
    fields["SignatureValue"] = _sign("500.00", "order-key-1")
    request = WebhookRequest(
        body=json.dumps(fields).encode(),
        headers={"content-type": "application/json"},
        query={},
        client_ip=None,
    )

    result = await _gateway().parse_webhook(request)

    assert result is not None
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_pending_status_is_a_noop() -> None:
    fields = {
        "InvId": "order-key-1",
        "OutSum": "500.00",
        "Status": "NEW",
        "TrsId": "trs-1",
    }
    fields["SignatureValue"] = _sign("500.00", "order-key-1")

    result = await _gateway().parse_webhook(_webhook_form(fields))

    assert result is None


async def test_parse_webhook_invalid_signature_raises() -> None:
    fields = {
        "InvId": "order-key-1",
        "OutSum": "500.00",
        "Status": "SUCCESS",
        "SignatureValue": "deadbeef",
    }

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook_form(fields))


async def test_parse_webhook_missing_fields_raises() -> None:
    fields = {"InvId": "order-key-1", "OutSum": "500.00"}

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook_form(fields))


async def test_webhook_ack_is_status_ok_json() -> None:
    fields = {
        "InvId": "order-key-1",
        "OutSum": "500.00",
        "Status": "SUCCESS",
        "TrsId": "trs-1",
    }
    fields["SignatureValue"] = _sign("500.00", "order-key-1")
    gateway = _gateway()

    result = await gateway.parse_webhook(_webhook_form(fields))

    assert gateway.webhook_ack(result) == '{"status": "ok"}'
