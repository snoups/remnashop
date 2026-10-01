import base64
import hashlib
import hmac
from urllib.parse import urlencode

import pytest

import app.modules.transactions.gateways.cloudpayments as cloudpayments_module
from app.core.enums import TransactionStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.cloudpayments import CloudPaymentsGateway
from tests.modules.transactions.gateways.support import (
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    install_http,
    json_response,
    make_order,
    webhook,
)

_SETTINGS = {"public_id": "pk_1", "api_secret": "secret"}


def _gateway() -> CloudPaymentsGateway:
    return CloudPaymentsGateway(settings=_SETTINGS, webhook_url=WEBHOOK_URL, return_url=RETURN_URL)


def _signed(status: str = "Completed") -> tuple[bytes, dict[str, str]]:
    raw = urlencode(
        {
            "TransactionId": "5",
            "Amount": "500.00",
            "Currency": "RUB",
            "InvoiceId": ORDER_REF,
            "Status": status,
            "AuthCode": "A1B2C3",
        }
    ).encode()
    signature = base64.b64encode(hmac.new(b"secret", raw, hashlib.sha256).digest()).decode()
    return raw, {"Content-HMAC": signature}


def _find(status: str = "Completed", success: bool = True) -> dict[str, object]:
    return {
        "Success": success,
        "Model": {
            "TransactionId": 5,
            "Amount": 500.0,
            "Currency": "RUB",
            "InvoiceId": ORDER_REF,
            "Status": status,
        },
    }


async def test_parse_webhook_verifies_the_raw_body_hmac() -> None:
    raw, headers = _signed()
    gateway = _gateway()
    signal = await gateway.parse_webhook(webhook(raw, headers))

    assert signal is not None and signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "5"
    assert gateway.webhook_ack(signal).body == '{"code": 0}'
    assert gateway.webhook_ack(signal).media_type == "application/json"

    with pytest.raises(PaymentGatewayError):
        await gateway.parse_webhook(webhook(raw, {"Content-HMAC": "AAAA"}))


async def test_parse_webhook_authorized_is_not_a_payment() -> None:
    raw, headers = _signed("Authorized")
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None and signal.claims_paid is False
    assert signal.reported_status is None


async def test_parse_webhook_declined_reports_failed() -> None:
    raw, headers = _signed("Declined")
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None and signal.claims_paid is False
    assert signal.reported_status is TransactionStatus.FAILED


async def test_confirm_finds_the_payment_by_invoice_id(monkeypatch: pytest.MonkeyPatch) -> None:
    http = install_http(monkeypatch, cloudpayments_module, json_response(_find()))
    raw, headers = _signed()
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None

    confirmed = await _gateway().confirm(make_order(), signal)

    expected_auth = "Basic " + base64.b64encode(b"pk_1:secret").decode()
    assert confirmed is not None and confirmed.provider_payment_id == "5"
    assert http.last.url.path == "/payments/find"
    assert http.last_json() == {"InvoiceId": ORDER_REF}
    assert http.last.headers["Authorization"] == expected_auth


@pytest.mark.parametrize("response", [_find("Authorized"), _find(success=False)])
async def test_confirm_rejects_unfinished_or_unknown_payments(
    monkeypatch: pytest.MonkeyPatch, response: dict[str, object]
) -> None:
    install_http(monkeypatch, cloudpayments_module, json_response(response))
    raw, headers = _signed()
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None
    assert await _gateway().confirm(make_order(), signal) is None
