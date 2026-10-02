import httpx
import pytest

from app.core.enums import TransactionStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.base import PaymentHttpClient
from app.modules.transactions.gateways.yookassa import YooKassaGateway
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

_SETTINGS = {"shop_id": "1000", "api_key": "test_key"}


def _gateway(*, http: PaymentHttpClient = NO_HTTP) -> YooKassaGateway:
    return YooKassaGateway(
        settings=_SETTINGS, webhook_url=WEBHOOK_URL, return_url=RETURN_URL, http=http
    )


def _payment(**overrides: object) -> dict[str, object]:
    payment: dict[str, object] = {
        "id": "yk-1",
        "status": "succeeded",
        "paid": True,
        "amount": {"value": "500.00", "currency": "RUB"},
        "metadata": {"order_ref": ORDER_REF},
    }
    payment.update(overrides)
    return payment


async def test_create_payment_sends_idempotence_key_and_order_ref() -> None:
    http = HttpRecorder(
        json_response({"id": "yk-1", "confirmation": {"confirmation_url": "https://pay/1"}}),
    )

    intent = await _gateway(http=http.client).create_payment(make_order())

    assert intent.provider_payment_id == "yk-1"
    assert intent.confirmation_url == "https://pay/1"
    assert http.last.headers["Idempotence-Key"] == ORDER_REF
    assert http.last_json()["metadata"] == {"order_ref": ORDER_REF}


async def test_parse_webhook_flags_only_payment_succeeded() -> None:
    paid = await _gateway().parse_webhook(
        webhook({"event": "payment.succeeded", "object": _payment()})
    )
    refund = await _gateway().parse_webhook(
        webhook({"event": "refund.succeeded", "object": {"id": "rf-1", "status": "succeeded"}})
    )

    assert paid is not None and paid.claims_paid is True
    assert paid.reference == ORDER_REF
    assert paid.provider_payment_id == "yk-1"
    assert refund is not None and refund.claims_paid is False


async def test_parse_webhook_payment_canceled_reports_canceled() -> None:
    signal = await _gateway().parse_webhook(
        webhook({"event": "payment.canceled", "object": _payment(status="canceled")})
    )
    assert signal is not None and signal.claims_paid is False
    assert signal.reported_status is TransactionStatus.CANCELED


async def test_parse_webhook_rejects_malformed_body() -> None:
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(b"not json"))


async def test_fetch_payment_reads_the_payment_with_the_api_timeout() -> None:
    http = HttpRecorder(json_response(_payment()))
    order = make_order(external_payment_id="yk-1")
    signal = await _gateway(http=http.client).parse_webhook(
        webhook({"event": "payment.succeeded", "object": _payment()})
    )
    assert signal is not None

    confirmed = await _gateway(http=http.client).confirm(order, signal)

    assert confirmed is not None
    assert confirmed.provider_payment_id == "yk-1"
    assert http.last.url.path == "/v3/payments/yk-1"
    assert http.last.extensions["timeout"]["read"] == 8.0


async def test_confirm_rejects_when_the_api_reports_pending() -> None:
    http = HttpRecorder(json_response(_payment(status="pending", paid=False)))
    signal = await _gateway(http=http.client).parse_webhook(
        webhook({"event": "payment.succeeded", "object": _payment()})
    )
    assert signal is not None

    assert (
        await _gateway(http=http.client).confirm(make_order(external_payment_id="yk-1"), signal)
        is None
    )


async def test_fetch_payment_without_a_stored_id_is_not_paid() -> None:
    signal = await _gateway().parse_webhook(
        webhook({"event": "payment.succeeded", "object": _payment()})
    )
    assert signal is not None
    assert await _gateway().confirm(make_order(), signal) is None


async def test_fetch_payment_propagates_http_errors() -> None:
    http = HttpRecorder(lambda request: httpx.Response(500))
    signal = await _gateway(http=http.client).parse_webhook(
        webhook({"event": "payment.succeeded", "object": _payment()})
    )
    assert signal is not None
    with pytest.raises(httpx.HTTPStatusError):
        await _gateway(http=http.client).confirm(make_order(external_payment_id="yk-1"), signal)


async def test_parse_webhook_refund_reports_refunded_against_the_payment() -> None:
    signal = await _gateway().parse_webhook(
        webhook(
            {
                "event": "refund.succeeded",
                "object": {"id": "rf-1", "payment_id": "yk-1", "status": "succeeded"},
            }
        )
    )
    assert signal is not None and signal.claims_paid is False
    assert signal.reported_status is TransactionStatus.REFUNDED
    assert signal.provider_payment_id == "yk-1"
