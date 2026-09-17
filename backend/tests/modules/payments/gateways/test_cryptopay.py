import hashlib
import hmac
import json

import pytest

import app.modules.payments.gateways.cryptopay as cryptopay_module
from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.cryptopay import CryptoPayGateway
from tests.modules.payments.gateways.support import (
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    install_http,
    json_response,
    make_order,
    webhook,
)

_TOKEN = "123:ABC"


def _gateway() -> CryptoPayGateway:
    return CryptoPayGateway(
        settings={"api_key": _TOKEN}, webhook_url=WEBHOOK_URL, return_url=RETURN_URL
    )


def _order() -> PaymentOrderDto:
    return make_order(currency=Currency.USD)


def _invoice(status: str = "paid") -> dict[str, object]:
    return {
        "invoice_id": 99,
        "status": status,
        "amount": "500",
        "currency_type": "fiat",
        "fiat": "USD",
        "payload": ORDER_REF,
    }


def _signed_update(update_type: str = "invoice_paid") -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(
        {
            "update_id": 1,
            "update_type": update_type,
            "request_date": "2026-09-17T10:00:00Z",
            "payload": _invoice(),
        }
    ).encode()
    secret = hashlib.sha256(_TOKEN.encode()).digest()
    signature = hmac.new(secret, raw, hashlib.sha256).hexdigest()
    return raw, {"crypto-pay-api-signature": signature}


async def test_create_payment_sets_expiry_and_stores_the_invoice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = install_http(
        monkeypatch,
        cryptopay_module,
        json_response({"ok": True, "result": {"invoice_id": 99, "bot_invoice_url": "https://t/1"}}),
    )

    intent = await _gateway().create_payment(_order())

    body = http.last_json()
    assert 0 < body["expires_in"] <= 1800
    assert body["payload"] == ORDER_REF
    assert http.last.headers["Crypto-Pay-API-Token"] == _TOKEN
    assert intent.provider_payment_id == "99"


async def test_parse_webhook_verifies_the_signature() -> None:
    raw, headers = _signed_update()
    signal = await _gateway().parse_webhook(webhook(raw, headers))

    assert signal is not None and signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "99"

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(raw, {"crypto-pay-api-signature": "00"}))


async def test_parse_webhook_ignores_other_updates() -> None:
    raw, headers = _signed_update("invoice_expired")
    assert await _gateway().parse_webhook(webhook(raw, headers)) is None


async def test_confirm_reads_get_invoices(monkeypatch: pytest.MonkeyPatch) -> None:
    http = install_http(
        monkeypatch,
        cryptopay_module,
        json_response({"ok": True, "result": {"items": [_invoice()]}}),
    )
    raw, headers = _signed_update()
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None

    order = make_order(currency=Currency.USD, external_payment_id="99")
    confirmed = await _gateway().confirm(order, signal)

    assert confirmed is not None
    assert http.last.url.path == "/api/getInvoices"
    assert http.last.url.params["invoice_ids"] == "99"


@pytest.mark.parametrize("items", [[], [_invoice("active")]])
async def test_confirm_rejects_missing_or_unpaid_invoices(
    monkeypatch: pytest.MonkeyPatch, items: list[dict[str, object]]
) -> None:
    install_http(
        monkeypatch, cryptopay_module, json_response({"ok": True, "result": {"items": items}})
    )
    raw, headers = _signed_update()
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None
    order = make_order(currency=Currency.USD, external_payment_id="99")
    assert await _gateway().confirm(order, signal) is None


async def test_confirm_raises_when_the_api_says_not_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    install_http(monkeypatch, cryptopay_module, json_response({"ok": False, "error": "x"}))
    raw, headers = _signed_update()
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None
    order = make_order(currency=Currency.USD, external_payment_id="99")
    with pytest.raises(PaymentGatewayError):
        await _gateway().confirm(order, signal)
