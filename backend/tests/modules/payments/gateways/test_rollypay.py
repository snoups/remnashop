import hashlib
import hmac
import json

import pytest

import app.modules.payments.gateways.rollypay as rollypay_module
from app.core.enums import PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.gateways.rollypay import RollyPayGateway
from tests.modules.payments.gateways.support import (
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    install_http,
    json_response,
    make_order,
    webhook,
)

_SETTINGS = {"api_key": "rpk", "signing_secret": "whsec"}


def _gateway() -> RollyPayGateway:
    return RollyPayGateway(settings=_SETTINGS, webhook_url=WEBHOOK_URL, return_url=RETURN_URL)


def _payment(**overrides: object) -> dict[str, object]:
    payment: dict[str, object] = {
        "payment_id": "pay-1",
        "order_id": ORDER_REF,
        "status": "paid",
        "amount": "500.00",
        "payment_currency": "RUB",
    }
    payment.update(overrides)
    return payment


def _signed(**overrides: object) -> tuple[bytes, dict[str, str]]:
    body = {"event_type": "payment.paid", **_payment(), "test": False}
    body.update(overrides)
    raw = json.dumps(body).encode()
    timestamp = "1740441600"
    signature = hmac.new(b"whsec", timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return raw, {"X-Signature": signature, "X-Timestamp": timestamp}


async def test_create_payment_sends_a_fresh_nonce(monkeypatch: pytest.MonkeyPatch) -> None:
    http = install_http(
        monkeypatch,
        rollypay_module,
        json_response({"payment_id": "pay-1", "pay_url": "https://rolly/1"}),
    )

    intent = await _gateway().create_payment(make_order())

    assert http.last.headers["X-API-Key"] == "rpk"
    assert http.last.headers["X-Nonce"]
    assert http.last_json()["order_id"] == ORDER_REF
    assert intent.provider_payment_id == "pay-1"


async def test_parse_webhook_verifies_timestamped_signature() -> None:
    raw, headers = _signed()
    signal = await _gateway().parse_webhook(webhook(raw, headers))

    assert signal is not None and signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "pay-1"

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(raw, {**headers, "X-Timestamp": "1"}))


async def test_parse_webhook_sandbox_and_unpaid_events_do_not_claim() -> None:
    for overrides in ({"test": True}, {"status": "expired", "event_type": "payment.expired"}):
        raw, headers = _signed(**overrides)
        signal = await _gateway().parse_webhook(webhook(raw, headers))
        assert signal is not None and signal.claims_paid is False


@pytest.mark.parametrize(
    ("status", "reported_status"),
    [
        ("canceled", PaymentOrderStatus.CANCELED),
        ("expired", PaymentOrderStatus.CANCELED),
        ("refunded", PaymentOrderStatus.REFUNDED),
        ("chargeback", PaymentOrderStatus.REFUNDED),
    ],
)
async def test_parse_webhook_reports_unpaid_outcomes(
    status: str, reported_status: PaymentOrderStatus
) -> None:
    raw, headers = _signed(status=status, event_type=f"payment.{status}")
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None and signal.reported_status is reported_status


async def test_confirm_reads_the_payment(monkeypatch: pytest.MonkeyPatch) -> None:
    http = install_http(monkeypatch, rollypay_module, json_response(_payment()))
    raw, headers = _signed()
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None

    confirmed = await _gateway().confirm(make_order(external_payment_id="pay-1"), signal)

    assert confirmed is not None
    assert http.last.url.path == "/api/v1/payments/pay-1"
    assert http.last.headers["X-Nonce"]


async def test_confirm_falls_back_to_signalled_payment_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = install_http(monkeypatch, rollypay_module, json_response(_payment()))
    raw, headers = _signed()
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None

    confirmed = await _gateway().confirm(make_order(external_payment_id=None), signal)

    assert confirmed is not None
    assert http.last.url.path == "/api/v1/payments/pay-1"
    assert http.last.headers["X-Nonce"]


@pytest.mark.parametrize("payment", [_payment(status="created"), _payment(test=True)])
async def test_confirm_rejects_unpaid_or_sandbox_payments(
    monkeypatch: pytest.MonkeyPatch, payment: dict[str, object]
) -> None:
    install_http(monkeypatch, rollypay_module, json_response(payment))
    raw, headers = _signed()
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None
    assert await _gateway().confirm(make_order(external_payment_id="pay-1"), signal) is None
