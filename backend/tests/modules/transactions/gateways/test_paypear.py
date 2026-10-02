import base64

import pytest

from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.base import PaymentHttpClient
from app.modules.transactions.gateways.common import format_utc
from app.modules.transactions.gateways.paypear import PayPearGateway
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

_SETTINGS = {"shop_id": "33661", "secret_key": "secret"}


def _gateway(*, http: PaymentHttpClient = NO_HTTP) -> PayPearGateway:
    return PayPearGateway(
        settings=_SETTINGS, webhook_url=WEBHOOK_URL, return_url=RETURN_URL, http=http
    )


def _payment(status: str = "CONFIRMED") -> dict[str, object]:
    return {
        "id": "pp-1",
        "shop_id": 33661,
        "order_id": ORDER_REF,
        "status": status,
        "amount": {"value": 500.0, "currency": "RUB"},
    }


def _notification(event: str = "payment.confirmed") -> dict[str, object]:
    return {"type": "notification", "event": event, "object": _payment(), "signature": "x"}


async def test_create_payment_sends_idempotency_key_expiry_and_basic_auth() -> None:
    http = HttpRecorder(
        json_response(
            {
                "success": True,
                "result": {"id": "pp-1", "confirmation": {"confirmation_url": "https://pp/1"}},
            }
        ),
    )
    order = make_order()

    intent = await _gateway(http=http.client).create_payment(order)

    body = http.last_json()
    expected_auth = "Basic " + base64.b64encode(b"33661:secret").decode()
    assert intent.provider_payment_id == "pp-1"
    assert body["expires_at"] == format_utc(order.expires_at)
    assert http.last.headers["Idempotence-Key"] == ORDER_REF
    assert http.last.headers["Idempotency-Key"] == ORDER_REF
    assert http.last.headers["Authorization"] == expected_auth


async def test_parse_webhook_needs_no_signature_and_flags_confirmed() -> None:
    confirmed = await _gateway().parse_webhook(webhook(_notification()))
    canceled = await _gateway().parse_webhook(webhook(_notification("payment.canceled")))

    assert confirmed is not None and confirmed.claims_paid is True
    assert confirmed.reference == ORDER_REF
    assert confirmed.provider_payment_id == "pp-1"
    assert canceled is not None and canceled.claims_paid is False


async def test_parse_webhook_requires_an_object_id() -> None:
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook({"event": "payment.confirmed", "object": {}}))


async def test_confirm_reads_the_payment() -> None:
    http = HttpRecorder(json_response({"success": True, "result": _payment()}))
    signal = await _gateway(http=http.client).parse_webhook(webhook(_notification()))
    assert signal is not None

    confirmed = await _gateway(http=http.client).confirm(
        make_order(external_payment_id="pp-1"), signal
    )

    assert confirmed is not None
    assert http.last.url.path == "/v1/payment/pp-1/"


async def test_confirm_rejects_a_forged_webhook() -> None:
    http = HttpRecorder(
        json_response({"success": True, "result": _payment(status="NEW")}),
    )
    signal = await _gateway(http=http.client).parse_webhook(webhook(_notification()))
    assert signal is not None

    assert (
        await _gateway(http=http.client).confirm(make_order(external_payment_id="pp-1"), signal)
        is None
    )
