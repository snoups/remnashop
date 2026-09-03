import hashlib
from datetime import timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlencode

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
from app.modules.payments.gateways.robokassa import RobokassaGateway
from tests.modules.subscriptions.factories import make_plan_snapshot

_SETTINGS = {"merchant_login": "shop-login", "password1": "pass1", "password2": "pass2"}
_WEBHOOK_URL = "https://shop.example/api/v1/payments/robokassa"
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
        "gateway_type": PaymentGatewayType.ROBOKASSA,
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


def _gateway() -> RobokassaGateway:
    return RobokassaGateway(settings=_SETTINGS, webhook_url=_WEBHOOK_URL, return_url=_RETURN_URL)


def _signed_webhook(
    out_sum: str, inv_id: str, shp_order_id: str, password2: str = "pass2"
) -> bytes:
    raw = f"{out_sum}:{inv_id}:{password2}:Shp_order_id={shp_order_id}"
    sign = hashlib.md5(raw.encode()).hexdigest().upper()
    return urlencode(
        {
            "OutSum": out_sum,
            "InvId": inv_id,
            "SignatureValue": sign,
            "Shp_order_id": shp_order_id,
        }
    ).encode()


def _webhook(body: bytes) -> WebhookRequest:
    return WebhookRequest(body=body, headers={}, query={}, client_ip=None)


async def test_create_payment_builds_a_signed_redirect_url() -> None:
    intent = await _gateway().create_payment(_order())

    assert intent.provider_payment_id is None
    assert intent.confirmation_url is not None
    assert intent.confirmation_url.startswith("https://auth.robokassa.ru/Merchant/Index.aspx?")
    params = {k: v[0] for k, v in parse_qs(intent.confirmation_url.split("?", 1)[1]).items()}
    assert params["MerchantLogin"] == "shop-login"
    assert params["OutSum"] == "500.00"
    assert params["Shp_order_id"] == "order-key-1"

    expected_sign = (
        hashlib.md5(b"shop-login:500.00:0:pass1:Shp_order_id=order-key-1").hexdigest().upper()
    )
    assert params["SignatureValue"] == expected_sign


async def test_parse_webhook_valid_signature_extracts_order_ref() -> None:
    body = _signed_webhook(out_sum="500.00", inv_id="0", shp_order_id="order-key-1")

    result = await _gateway().parse_webhook(_webhook(body))

    assert result is not None
    assert result.reference == "order-key-1"
    assert result.status is PaymentOrderStatus.PAID


async def test_parse_webhook_invalid_signature_raises() -> None:
    body = urlencode(
        {
            "OutSum": "500.00",
            "InvId": "0",
            "SignatureValue": "0" * 32,
            "Shp_order_id": "order-key-1",
        }
    ).encode()

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(body))


async def test_parse_webhook_missing_shp_order_id_raises() -> None:
    raw = "500.00:0:pass2"
    sign = hashlib.md5(raw.encode()).hexdigest().upper()
    body = urlencode({"OutSum": "500.00", "InvId": "0", "SignatureValue": sign}).encode()

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(_webhook(body))


async def test_webhook_ack_echoes_inv_id_after_parsing() -> None:
    gateway = _gateway()
    body = _signed_webhook(out_sum="500.00", inv_id="42", shp_order_id="order-key-1")

    result = await gateway.parse_webhook(_webhook(body))

    assert gateway.webhook_ack(result) == "OK42"
