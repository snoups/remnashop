import hashlib
import hmac
import json

import httpx
import pytest

from app.core.enums import TransactionStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.base import PaymentHttpClient
from app.modules.transactions.gateways.riopay import RioPayGateway
from app.modules.transactions.gateways.valutix import ValutixGateway
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

_GATEWAYS = [
    (RioPayGateway, "api_token", "api.riopay.online"),
    (ValutixGateway, "api_key", "api.panel.valutix.kz"),
]


def _gateway(
    cls: type[RioPayGateway] = RioPayGateway,
    token_setting: str = "api_token",
    *,
    http: PaymentHttpClient = NO_HTTP,
    **extra: str,
) -> RioPayGateway:
    settings = {token_setting: "tok", **extra}
    return cls(settings=settings, webhook_url=WEBHOOK_URL, return_url=RETURN_URL, http=http)


def _order_body(status: str = "COMPLETED") -> dict[str, object]:
    return {
        "id": "o-1",
        "status": status,
        "amount": "500.0",
        "currency": "RUB",
        "externalId": ORDER_REF,
    }


def _signed_hook(status: str = "COMPLETED") -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(_order_body(status)).encode()
    signature = hmac.new(b"tok", raw, hashlib.sha512).hexdigest().upper()
    return raw, {"X-Signature": signature}


@pytest.mark.parametrize(("cls", "token_setting", "host"), _GATEWAYS)
async def test_create_payment_sends_service_callback_and_fail_urls(
    cls: type[RioPayGateway], token_setting: str, host: str
) -> None:
    http = HttpRecorder(json_response({"id": "o-1", "paymentLink": "https://p/1"}, 201))

    intent = await _gateway(cls, token_setting, service_id="3", http=http.client).create_payment(
        make_order()
    )

    body = http.last_json()
    assert http.last.url.host == host
    assert http.last.url.path == "/v1/orders"
    assert http.last.headers["X-Api-Token"] == "tok"
    assert body["serviceId"] == 3
    assert body["callbackUrl"] == WEBHOOK_URL
    assert body["failUrl"] == RETURN_URL
    assert body["externalId"] == ORDER_REF
    assert body["amount"] == "500.00"
    assert intent.provider_payment_id == "o-1"


async def test_create_payment_accepts_200_without_a_service_id() -> None:
    http = HttpRecorder(json_response({"id": "o-1", "paymentLink": "https://p/1"}))
    await _gateway(http=http.client).create_payment(make_order())
    assert "serviceId" not in http.last_json()


async def test_create_payment_raises_on_an_api_error() -> None:
    http = HttpRecorder(lambda request: httpx.Response(422, json={"message": "bad"}))
    with pytest.raises(PaymentGatewayError):
        await _gateway(http=http.client).create_payment(make_order())


@pytest.mark.parametrize(("cls", "token_setting", "host"), _GATEWAYS)
async def test_parse_webhook_verifies_the_hmac_case_insensitively(
    cls: type[RioPayGateway], token_setting: str, host: str
) -> None:
    raw, headers = _signed_hook()
    signal = await _gateway(cls, token_setting).parse_webhook(webhook(raw, headers))

    assert signal is not None and signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "o-1"

    with pytest.raises(PaymentGatewayError):
        await _gateway(cls, token_setting).parse_webhook(webhook(raw, {"X-Signature": "00"}))


async def test_parse_webhook_failed_order_does_not_claim() -> None:
    raw, headers = _signed_hook("FAILED")
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None and signal.claims_paid is False
    assert signal.reported_status is TransactionStatus.FAILED


@pytest.mark.parametrize(
    ("status", "reported_status"),
    [("CANCELED", TransactionStatus.CANCELED), ("EXPIRED", TransactionStatus.CANCELED)],
)
async def test_parse_webhook_reports_canceled_and_expired_as_canceled(
    status: str, reported_status: TransactionStatus
) -> None:
    raw, headers = _signed_hook(status)
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None and signal.reported_status is reported_status


@pytest.mark.parametrize(("cls", "token_setting", "host"), _GATEWAYS)
async def test_confirm_reads_the_order(
    cls: type[RioPayGateway], token_setting: str, host: str
) -> None:
    http = HttpRecorder(json_response(_order_body()))
    raw, headers = _signed_hook()
    gateway = _gateway(cls, token_setting, http=http.client)
    signal = await gateway.parse_webhook(webhook(raw, headers))
    assert signal is not None

    confirmed = await gateway.confirm(make_order(external_payment_id="o-1"), signal)

    assert confirmed is not None
    assert http.last.url.host == host
    assert http.last.url.path == "/v1/orders/o-1"


async def test_confirm_rejects_a_failed_order() -> None:
    http = HttpRecorder(json_response(_order_body("FAILED")))
    raw, headers = _signed_hook()
    signal = await _gateway(http=http.client).parse_webhook(webhook(raw, headers))
    assert signal is not None
    assert (
        await _gateway(http=http.client).confirm(make_order(external_payment_id="o-1"), signal)
        is None
    )
