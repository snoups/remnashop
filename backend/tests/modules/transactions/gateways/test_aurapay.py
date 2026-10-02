import hashlib
import hmac
import json
from typing import Any

import pytest

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.aurapay import AuraPayGateway
from app.modules.transactions.gateways.base import PaymentHttpClient
from tests.modules.transactions.gateways.support import (
    NO_HTTP,
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    HttpRecorder,
    json_response,
    make_order,
    webhook,
)

_SETTINGS = {"api_key": "key", "shop_id": "shop-1", "secret_key": "secret2"}


def _gateway(*, http: PaymentHttpClient = NO_HTTP) -> AuraPayGateway:
    return AuraPayGateway(
        settings=_SETTINGS, webhook_url=WEBHOOK_URL, return_url=RETURN_URL, http=http
    )


def _docs_signature(params: dict[str, Any]) -> str:
    ordered = dict(sorted(params.items()))
    concatenated = "".join("" if v is None else str(v) for v in ordered.values())
    return hmac.new(b"secret2", concatenated.encode(), hashlib.sha256).hexdigest()


def _hook(status: str = "PAID") -> dict[str, Any]:
    return {
        "id": "inv-1",
        "amount": "500.00",
        "status": status,
        "comment": "Order #42",
        "service": "sbp",
        "shop_id": "shop-1",
        "order_id": ORDER_REF,
        "custom_fields": None,
    }


async def test_create_payment_sends_lifetime_in_minutes() -> None:
    http = HttpRecorder(
        json_response({"id": "inv-1", "payment_data": {"url": "https://aura/1"}}),
    )

    intent = await _gateway(http=http.client).create_payment(make_order())

    body = http.last_json()
    assert 1 <= body["lifetime"] <= 30
    assert body["order_id"] == ORDER_REF
    assert http.last.headers["X-ShopId"] == "shop-1"
    assert intent.provider_payment_id == "inv-1"


async def test_parse_webhook_matches_the_docs_signature() -> None:
    body = _hook()
    signal = await _gateway().parse_webhook(
        webhook(json.dumps(body).encode(), {"X-SIGNATURE": _docs_signature(body)})
    )

    assert signal is not None and signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "inv-1"


async def test_parse_webhook_rejects_tampering_and_ignores_unpaid() -> None:
    body = _hook()
    tampered = {**body, "amount": "1.00"}
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(
            webhook(json.dumps(tampered).encode(), {"X-SIGNATURE": _docs_signature(body)})
        )
    expired = _hook("EXPIRED")
    signal = await _gateway().parse_webhook(
        webhook(json.dumps(expired).encode(), {"X-SIGNATURE": _docs_signature(expired)})
    )
    assert signal is not None and signal.claims_paid is False


async def test_confirm_reads_invoice_status() -> None:
    http = HttpRecorder(
        json_response({"id": "inv-1", "order_id": ORDER_REF, "amount": 500, "status": "PAID"}),
    )
    body = _hook()
    signal = await _gateway(http=http.client).parse_webhook(
        webhook(json.dumps(body).encode(), {"X-SIGNATURE": _docs_signature(body)})
    )
    assert signal is not None

    confirmed = await _gateway(http=http.client).confirm(
        make_order(external_payment_id="inv-1"), signal
    )

    assert confirmed is not None
    assert http.last.url.path == "/invoice/status"
    assert http.last_json() == {"id": "inv-1"}


async def test_confirm_rejects_a_pending_invoice() -> None:
    http = HttpRecorder(
        json_response({"id": "inv-1", "order_id": ORDER_REF, "amount": 500, "status": "PENDING"}),
    )
    body = _hook()
    signal = await _gateway(http=http.client).parse_webhook(
        webhook(json.dumps(body).encode(), {"X-SIGNATURE": _docs_signature(body)})
    )
    assert signal is not None
    assert (
        await _gateway(http=http.client).confirm(make_order(external_payment_id="inv-1"), signal)
        is None
    )


async def test_confirm_rejects_a_usd_order() -> None:
    http = HttpRecorder(
        json_response({"id": "inv-1", "order_id": ORDER_REF, "amount": 500, "status": "PAID"}),
    )
    body = _hook()
    signal = await _gateway(http=http.client).parse_webhook(
        webhook(json.dumps(body).encode(), {"X-SIGNATURE": _docs_signature(body)})
    )
    assert signal is not None

    order = make_order(external_payment_id="inv-1", currency=Currency.USD)
    assert await _gateway(http=http.client).confirm(order, signal) is None
