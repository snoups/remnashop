import hashlib
from urllib.parse import urlencode

import pytest

from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.base import PaymentHttpClient
from app.modules.transactions.gateways.paypalych import PaypalychGateway
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

_TOKEN = "api-token"
_SETTINGS = {"api_token": _TOKEN, "shop_id": "shop-1"}


def _gateway(*, http: PaymentHttpClient = NO_HTTP) -> PaypalychGateway:
    return PaypalychGateway(
        settings=_SETTINGS, webhook_url=WEBHOOK_URL, return_url=RETURN_URL, http=http
    )


def _postback(status: str = "SUCCESS", out_sum: str = "500.00") -> dict[str, str]:
    signature = hashlib.md5(f"{out_sum}:{ORDER_REF}:{_TOKEN}".encode()).hexdigest().upper()
    return {
        "Status": status,
        "InvId": ORDER_REF,
        "OutSum": out_sum,
        "TrsId": "bill-1",
        "CurrencyIn": "RUB",
        "SignatureValue": signature,
    }


def _bill(status: str = "SUCCESS") -> dict[str, object]:
    return {
        "id": "bill-1",
        "order_id": ORDER_REF,
        "status": status,
        "amount": 500.0,
        "currency_in": "RUB",
        "success": True,
    }


async def test_create_payment_sends_ttl_and_bearer_token() -> None:
    http = HttpRecorder(
        json_response({"success": "true", "bill_id": "bill-1", "link_page_url": "https://p/1"}),
    )

    intent = await _gateway(http=http.client).create_payment(make_order())

    body = http.last_json()
    assert intent.provider_payment_id == "bill-1"
    assert intent.confirmation_url == "https://p/1"
    assert body["order_id"] == ORDER_REF
    assert 0 < body["ttl"] <= 1800
    assert http.last.headers["Authorization"] == f"Bearer {_TOKEN}"


async def test_create_payment_rejects_success_false() -> None:
    http = HttpRecorder(json_response({"success": "false", "message": "nope"}))
    with pytest.raises(PaymentGatewayError):
        await _gateway(http=http.client).create_payment(make_order())


@pytest.mark.parametrize("as_form", [True, False])
async def test_parse_webhook_verifies_signature_with_the_api_token(as_form: bool) -> None:
    body = _postback()
    request = webhook(urlencode(body).encode() if as_form else body)

    signal = await _gateway().parse_webhook(request)

    assert signal is not None
    assert signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "bill-1"


async def test_parse_webhook_rejects_a_bad_signature() -> None:
    body = {**_postback(), "SignatureValue": "0" * 32}
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(body))


@pytest.mark.parametrize(
    ("status", "claims"), [("OVERPAID", True), ("UNDERPAID", False), ("FAIL", False)]
)
async def test_parse_webhook_status_mapping(status: str, claims: bool) -> None:
    signal = await _gateway().parse_webhook(webhook(_postback(status=status)))
    assert signal is not None and signal.claims_paid is claims


async def test_confirm_reads_bill_status() -> None:
    http = HttpRecorder(json_response(_bill()))
    signal = await _gateway(http=http.client).parse_webhook(webhook(_postback()))
    assert signal is not None

    confirmed = await _gateway(http=http.client).confirm(
        make_order(external_payment_id="bill-1"), signal
    )

    assert confirmed is not None
    assert http.last.url.path == "/api/v1/bill/status"
    assert http.last.url.params["id"] == "bill-1"


async def test_confirm_rejects_a_replayed_signature_with_forged_status() -> None:
    # The signature does not cover Status, so a signed (OutSum, InvId) pair
    # from a failed payment verifies; only the API tells the truth.
    http = HttpRecorder(json_response(_bill(status="FAIL")))
    signal = await _gateway(http=http.client).parse_webhook(webhook(_postback(status="SUCCESS")))
    assert signal is not None

    assert (
        await _gateway(http=http.client).confirm(make_order(external_payment_id="bill-1"), signal)
        is None
    )
