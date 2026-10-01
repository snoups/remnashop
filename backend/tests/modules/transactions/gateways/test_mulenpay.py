import hashlib

import pytest

import app.modules.transactions.gateways.mulenpay as mulenpay_module
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.mulenpay import MulenPayGateway
from app.modules.transactions.gateways.urlpay import UrlPayGateway
from tests.modules.transactions.gateways.support import (
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    install_http,
    json_response,
    make_order,
    webhook,
)

_SETTINGS = {"api_key": "key", "secret_key": "secret", "shop_id": "5"}
_GATEWAYS = [(MulenPayGateway, "mulenpay.ru"), (UrlPayGateway, "urlpay.io")]


def _gateway(cls: type[MulenPayGateway] = MulenPayGateway, **settings: str) -> MulenPayGateway:
    return cls(settings={**_SETTINGS, **settings}, webhook_url=WEBHOOK_URL, return_url=RETURN_URL)


def _callback(status: str = "success") -> dict[str, object]:
    return {
        "id": 12345,
        "amount": 500.0,
        "currency": "rub",
        "uuid": ORDER_REF,
        "payment_status": status,
    }


def _payment(status: int = 3) -> dict[str, object]:
    return {
        "success": True,
        "payment": {
            "id": 12345,
            "uuid": ORDER_REF,
            "amount": "500.00",
            "currency": "rub",
            "status": status,
        },
    }


@pytest.mark.parametrize(("cls", "host"), _GATEWAYS)
async def test_create_payment_signs_lowercase_currency_and_stores_the_id(
    monkeypatch: pytest.MonkeyPatch, cls: type[MulenPayGateway], host: str
) -> None:
    http = install_http(
        monkeypatch,
        mulenpay_module,
        json_response({"success": True, "paymentUrl": "https://pay/1", "id": 12345}, 201),
    )

    intent = await _gateway(cls).create_payment(make_order())

    body = http.last_json()
    assert http.last.url.host == host
    assert http.last.url.path == "/api/v2/payments"
    assert intent.provider_payment_id == "12345"
    assert body["currency"] == "rub"
    assert body["sign"] == hashlib.sha1(b"rub500.005secret").hexdigest()
    assert body["items"][0]["vat_code"] == 0
    assert body["items"][0]["price"] == 500.0


async def test_create_payment_sends_the_buyer_email_and_return_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = install_http(
        monkeypatch,
        mulenpay_module,
        json_response({"success": True, "paymentUrl": "https://pay/1", "id": 1}, 201),
    )
    await _gateway().create_payment(make_order(customer_email="buyer@example.com"))
    assert http.last_json()["client"] == "buyer@example.com"
    assert http.last_json()["website_url"] == RETURN_URL

    await _gateway().create_payment(make_order())
    assert "client" not in http.last_json()


async def test_create_payment_uses_the_configured_vat_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = install_http(
        monkeypatch,
        mulenpay_module,
        json_response({"success": True, "paymentUrl": "https://pay/1", "id": 1}, 201),
    )
    await _gateway(vat_code="6").create_payment(make_order())
    assert http.last_json()["items"][0]["vat_code"] == 6


async def test_parse_webhook_needs_no_signature() -> None:
    paid = await _gateway().parse_webhook(webhook(_callback()))
    canceled = await _gateway().parse_webhook(webhook(_callback("cancel")))

    assert paid is not None and paid.claims_paid is True
    assert paid.reference == ORDER_REF
    assert paid.provider_payment_id == "12345"
    assert canceled is not None and canceled.claims_paid is False


async def test_parse_webhook_requires_the_uuid() -> None:
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook({"payment_status": "success"}))


@pytest.mark.parametrize(("cls", "host"), _GATEWAYS)
async def test_confirm_reads_the_payment(
    monkeypatch: pytest.MonkeyPatch, cls: type[MulenPayGateway], host: str
) -> None:
    http = install_http(monkeypatch, mulenpay_module, json_response(_payment()))
    signal = await _gateway(cls).parse_webhook(webhook(_callback()))
    assert signal is not None

    confirmed = await _gateway(cls).confirm(make_order(external_payment_id="12345"), signal)

    assert confirmed is not None
    assert http.last.url.host == host
    assert http.last.url.path == "/api/v2/payments/12345"
    assert http.last.headers["Authorization"] == "Bearer key"


@pytest.mark.parametrize("status", [0, 1, 2, 4, 5, 6])
async def test_confirm_rejects_unprocessed_statuses(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    install_http(monkeypatch, mulenpay_module, json_response(_payment(status)))
    signal = await _gateway().parse_webhook(webhook(_callback()))
    assert signal is not None
    assert await _gateway().confirm(make_order(external_payment_id="12345"), signal) is None
