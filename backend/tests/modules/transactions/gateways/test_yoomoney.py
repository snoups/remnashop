import hashlib
import hmac
from decimal import Decimal
from urllib.parse import quote, urlencode

import httpx
import pytest

import app.modules.transactions.gateways.yoomoney as yoomoney_module
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.yoomoney import YooMoneyGateway
from tests.modules.transactions.gateways.support import (
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    install_http,
    json_response,
    make_order,
    webhook,
)

_SETTINGS = {"wallet_id": "41001", "secret_key": "secret"}


def _gateway(**extra: str) -> YooMoneyGateway:
    return YooMoneyGateway(
        settings={**_SETTINGS, **extra}, webhook_url=WEBHOOK_URL, return_url=RETURN_URL
    )


def _notification(**overrides: str) -> bytes:
    fields = {
        "notification_type": "p2p-incoming",
        "operation_id": "op-1",
        "amount": "490.00",
        "withdraw_amount": "500.00",
        "currency": "643",
        "datetime": "2026-09-17T10:00:00Z",
        "sender": "41002",
        "codepro": "false",
        "label": ORDER_REF,
        "unaccepted": "false",
    }
    fields.update(overrides)
    base = "&".join(f"{key}={quote(value, safe='')}" for key, value in sorted(fields.items()))
    fields["sign"] = hmac.new(b"secret", base.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields).encode()


def _details(**overrides: object) -> dict[str, object]:
    details: dict[str, object] = {
        "operation_id": "op-1",
        "status": "success",
        "direction": "in",
        "amount": 490.0,
        "label": ORDER_REF,
    }
    details.update(overrides)
    return details


async def test_create_payment_follows_the_quickpay_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/quickpay/confirm.xml":
            return httpx.Response(302, headers={"Location": "https://yoomoney.ru/quickpay/pay/1"})
        return httpx.Response(200)

    http = install_http(monkeypatch, yoomoney_module, respond)

    intent = await _gateway().create_payment(make_order())

    assert intent.confirmation_url == "https://yoomoney.ru/quickpay/pay/1"
    assert b"label=order-key-1" in http.requests[0].content


async def test_parse_webhook_verifies_the_signature() -> None:
    signal = await _gateway().parse_webhook(webhook(_notification()))

    assert signal is not None and signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "op-1"
    assert signal.amount == Decimal("500.00")


async def test_parse_webhook_rejects_a_bad_signature_and_skips_test_pings() -> None:
    tampered = _notification().replace(b"withdraw_amount=500.00", b"withdraw_amount=1.00")
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(tampered))
    ping = await _gateway().parse_webhook(webhook(_notification(operation_id="test-notification")))
    assert ping is None


@pytest.mark.parametrize("field", ["unaccepted", "codepro"])
async def test_parse_webhook_does_not_claim_payment_when_unaccepted_or_codepro(field: str) -> None:
    signal = await _gateway().parse_webhook(webhook(_notification(**{field: "true"})))

    assert signal is not None and signal.claims_paid is False


async def test_confirm_without_a_token_trusts_the_signed_amount() -> None:
    gateway = _gateway()
    paid = await gateway.parse_webhook(webhook(_notification()))
    short = await gateway.parse_webhook(webhook(_notification(withdraw_amount="400.00")))
    missing = await gateway.parse_webhook(webhook(_notification(withdraw_amount="")))
    assert paid is not None and short is not None and missing is not None

    assert await gateway.confirm(make_order(), paid) is not None
    assert await gateway.confirm(make_order(), short) is None
    assert await gateway.confirm(make_order(), missing) is None


async def test_confirm_with_a_token_reads_operation_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = install_http(monkeypatch, yoomoney_module, json_response(_details()))
    gateway = _gateway(access_token="wallet-token")
    signal = await gateway.parse_webhook(webhook(_notification()))
    assert signal is not None

    confirmed = await gateway.confirm(make_order(), signal)

    assert confirmed is not None and confirmed.amount == Decimal("500.00")
    assert http.last.url.path == "/api/operation-details"
    assert http.last.headers["Authorization"] == "Bearer wallet-token"
    assert http.last.content == b"operation_id=op-1"


@pytest.mark.parametrize(
    "details", [_details(direction="out"), _details(status="refused"), _details(label="other")]
)
async def test_confirm_with_a_token_rejects_mismatches(
    monkeypatch: pytest.MonkeyPatch, details: dict[str, object]
) -> None:
    install_http(monkeypatch, yoomoney_module, json_response(details))
    gateway = _gateway(access_token="wallet-token")
    signal = await gateway.parse_webhook(webhook(_notification()))
    assert signal is not None
    assert await gateway.confirm(make_order(), signal) is None


async def test_confirm_with_a_token_raises_on_api_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    install_http(monkeypatch, yoomoney_module, json_response({"error": "invalid_token"}))
    gateway = _gateway(access_token="wallet-token")
    signal = await gateway.parse_webhook(webhook(_notification()))
    assert signal is not None
    with pytest.raises(PaymentGatewayError):
        await gateway.confirm(make_order(), signal)
