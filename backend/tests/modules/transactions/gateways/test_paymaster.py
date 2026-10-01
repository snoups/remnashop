import pytest

import app.modules.transactions.gateways.paymaster as paymaster_module
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.common import format_utc
from app.modules.transactions.gateways.paymaster import PayMasterGateway
from tests.modules.transactions.gateways.support import (
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    install_http,
    json_response,
    make_order,
    webhook,
)

_SETTINGS = {"merchant_id": "m-1", "api_key": "token"}


def _gateway() -> PayMasterGateway:
    return PayMasterGateway(settings=_SETTINGS, webhook_url=WEBHOOK_URL, return_url=RETURN_URL)


def _payment(**overrides: object) -> dict[str, object]:
    payment: dict[str, object] = {
        "id": "9755",
        "status": "Settled",
        "amount": {"value": 500.0, "currency": "RUB"},
        "invoice": {"description": "Order #42", "orderNo": ORDER_REF},
    }
    payment.update(overrides)
    return payment


async def test_create_payment_sends_order_no_expiry_and_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = install_http(
        monkeypatch,
        paymaster_module,
        json_response({"paymentId": "9755", "url": "https://paymaster.ru/pay/1"}),
    )
    order = make_order()

    intent = await _gateway().create_payment(order)

    body = http.last_json()
    assert intent.provider_payment_id == "9755"
    assert intent.confirmation_url == "https://paymaster.ru/pay/1"
    assert body["invoice"]["orderNo"] == ORDER_REF
    assert body["invoice"]["expires"] == format_utc(order.expires_at)
    assert http.last.headers["Idempotency-Key"] == ORDER_REF
    assert http.last.headers["Authorization"] == "Bearer token"


async def test_create_payment_requires_a_payment_id(monkeypatch: pytest.MonkeyPatch) -> None:
    install_http(monkeypatch, paymaster_module, json_response({"url": "https://pay"}))
    with pytest.raises(PaymentGatewayError):
        await _gateway().create_payment(make_order())


async def test_parse_webhook_claims_paid_only_when_settled() -> None:
    settled = await _gateway().parse_webhook(webhook(_payment()))
    authorized = await _gateway().parse_webhook(webhook(_payment(status="Authorized")))

    assert settled is not None and settled.claims_paid is True
    assert settled.provider_payment_id == "9755"
    assert settled.reference == ORDER_REF
    assert authorized is not None and authorized.claims_paid is False


async def test_parse_webhook_requires_an_id() -> None:
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook({"status": "Settled"}))


async def test_confirm_reads_the_stored_payment(monkeypatch: pytest.MonkeyPatch) -> None:
    http = install_http(monkeypatch, paymaster_module, json_response(_payment()))
    signal = await _gateway().parse_webhook(webhook(_payment()))
    assert signal is not None

    confirmed = await _gateway().confirm(make_order(external_payment_id="9755"), signal)

    assert confirmed is not None
    assert http.last.url.path == "/api/v2/payments/9755"


async def test_confirm_rejects_a_forged_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    install_http(monkeypatch, paymaster_module, json_response(_payment(status="Authorized")))
    signal = await _gateway().parse_webhook(webhook(_payment()))
    assert signal is not None

    assert await _gateway().confirm(make_order(external_payment_id="9755"), signal) is None


async def test_confirm_rejects_a_payment_without_order_no(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_http(
        monkeypatch, paymaster_module, json_response(_payment(invoice={"description": "Order"}))
    )
    signal = await _gateway().parse_webhook(webhook(_payment()))
    assert signal is not None

    assert await _gateway().confirm(make_order(external_payment_id="9755"), signal) is None


async def test_confirm_rejects_a_different_order_no(monkeypatch: pytest.MonkeyPatch) -> None:
    install_http(monkeypatch, paymaster_module, json_response(_payment(invoice={"orderNo": "x"})))
    signal = await _gateway().parse_webhook(webhook(_payment()))
    assert signal is not None

    assert await _gateway().confirm(make_order(external_payment_id="9755"), signal) is None
