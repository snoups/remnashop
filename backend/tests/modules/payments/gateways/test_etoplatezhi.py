import base64
import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from urllib.parse import parse_qs

import pytest

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
from app.modules.payments.gateways.etoplatezhi import EtoplatezhiGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"project_id": "77", "secret_key": "etp-secret"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/etoplatezhi"
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
        "gateway_type": PaymentGatewayType.ETOPLATEZHI,
        "status": PaymentOrderStatus.PENDING,
        "base_price": Decimal("500"),
        "discount_percent": 0,
        "discount_source": DiscountSource.NONE,
        "final_price": Decimal("500.00"),
        "idempotency_key": "order-key-1",
        "expires_at": datetime_now() + timedelta(minutes=30),
    }
    defaults.update(overrides)
    return PaymentOrderDto(**defaults)  # type: ignore[arg-type]


def _gateway() -> EtoplatezhiGateway:
    return EtoplatezhiGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _flatten(params: dict, prefix: str = "") -> list[str]:
    entries = []
    for key, value in params.items():
        if key in {"frame_mode", "signature"}:
            continue
        full_key = f"{prefix}:{key}" if prefix else key
        if isinstance(value, dict):
            entries.extend(_flatten(value, full_key))
        elif value is not None:
            entries.append(f"{full_key}:{value}")
    return entries


def _sign(params: dict, secret: str = "etp-secret") -> str:
    entries = sorted(_flatten(params))
    message = ";".join(entries)
    digest = hmac.new(secret.encode(), message.encode(), hashlib.sha512).digest()
    return base64.b64encode(digest).decode()


async def test_create_payment_builds_a_signed_url_with_no_network_call() -> None:
    intent = await _gateway().create_payment(_order())

    assert intent.provider_payment_id is None
    assert intent.confirmation_url is not None
    assert intent.confirmation_url.startswith("https://paymentpage.etoplatezhi.ru/payment?")
    params = {k: v[0] for k, v in parse_qs(intent.confirmation_url.split("?", 1)[1]).items()}
    assert params["project_id"] == "77"
    assert params["payment_id"] == "order-key-1"
    assert params["payment_amount"] == "50000"
    assert params["payment_currency"] == "RUB"

    signed_params = dict(params)
    received_sig = signed_params.pop("signature")
    assert received_sig == _sign(signed_params)


def _webhook(payload: dict[str, object]) -> WebhookRequest:
    return WebhookRequest(body=json.dumps(payload).encode(), headers={}, query={}, client_ip=None)


def _signed_webhook(payment: dict[str, object]) -> WebhookRequest:
    payload = {"project_id": 77, "payment": payment, "customer": {"id": "1"}}
    payload["signature"] = _sign(payload)
    return _webhook(payload)


async def test_parse_webhook_success_status_returns_result() -> None:
    result = await _gateway().parse_webhook(
        _signed_webhook({"id": "order-key-1", "status": "success"})
    )

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_invalid_signature_raises() -> None:
    payload = {
        "project_id": 77,
        "payment": {"id": "order-key-1", "status": "success"},
        "signature": "deadbeef",
    }
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(payload))


async def test_parse_webhook_missing_signature_raises() -> None:
    payload = {"project_id": 77, "payment": {"id": "order-key-1", "status": "success"}}
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(payload))


async def test_parse_webhook_non_success_status_is_a_noop() -> None:
    result = await _gateway().parse_webhook(
        _signed_webhook({"id": "order-key-1", "status": "processing"})
    )
    assert result is None
