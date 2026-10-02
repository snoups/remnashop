import hashlib
import hmac
import json

import pytest

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.base import PaymentHttpClient
from app.modules.transactions.gateways.lava import LavaGateway
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

_SETTINGS = {"shop_id": "shop-1", "secret_key": "secret", "webhook_secret": "extra"}


def _gateway(*, http: PaymentHttpClient = NO_HTTP) -> LavaGateway:
    return LavaGateway(
        settings=_SETTINGS, webhook_url=WEBHOOK_URL, return_url=RETURN_URL, http=http
    )


def _sign(key: str, body: bytes) -> str:
    return hmac.new(key.encode(), body, hashlib.sha256).hexdigest()


def _hook(status: str = "success") -> bytes:
    return json.dumps(
        {"invoice_id": "inv-1", "order_id": ORDER_REF, "status": status, "amount": 500.0}
    ).encode()


def _status(status: str = "success") -> dict[str, object]:
    return {
        "data": {"id": "inv-1", "status": status, "amount": 500.0, "order_id": ORDER_REF},
        "status": 200,
        "status_check": True,
    }


async def test_create_payment_signs_the_exact_body_and_sends_expire() -> None:
    http = HttpRecorder(
        json_response(
            {"data": {"id": "inv-1", "url": "https://lava/1"}, "status": 200, "status_check": True}
        ),
    )

    intent = await _gateway(http=http.client).create_payment(make_order())

    payload = json.loads(http.last.content)
    assert http.last.headers["Signature"] == _sign("secret", http.last.content)
    assert payload["orderId"] == ORDER_REF
    assert 0 < payload["expire"] <= 30
    assert intent.provider_payment_id == "inv-1"
    assert intent.confirmation_url == "https://lava/1"


async def test_parse_webhook_reads_the_signature_header() -> None:
    raw = _hook()
    signal = await _gateway().parse_webhook(webhook(raw, {"Signature": _sign("extra", raw)}))

    assert signal is not None and signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "inv-1"


async def test_parse_webhook_rejects_other_headers_and_keys() -> None:
    raw = _hook()
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(raw, {"Authorization": _sign("extra", raw)}))
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(raw, {"Signature": _sign("secret", raw)}))


async def test_parse_webhook_failed_invoice_does_not_claim_payment() -> None:
    raw = _hook("fail")
    signal = await _gateway().parse_webhook(webhook(raw, {"Signature": _sign("extra", raw)}))
    assert signal is not None and signal.claims_paid is False


async def test_confirm_posts_a_signed_status_request() -> None:
    http = HttpRecorder(json_response(_status()))
    raw = _hook()
    signal = await _gateway(http=http.client).parse_webhook(
        webhook(raw, {"Signature": _sign("extra", raw)})
    )
    assert signal is not None

    confirmed = await _gateway(http=http.client).confirm(make_order(), signal)

    assert confirmed is not None
    assert http.last.url.path == "/business/invoice/status"
    assert http.last.headers["Signature"] == _sign("secret", http.last.content)
    assert json.loads(http.last.content) == {"shopId": "shop-1", "orderId": ORDER_REF}


async def test_confirm_rejects_an_unpaid_invoice() -> None:
    http = HttpRecorder(json_response(_status("created")))
    raw = _hook()
    signal = await _gateway(http=http.client).parse_webhook(
        webhook(raw, {"Signature": _sign("extra", raw)})
    )
    assert signal is not None
    assert await _gateway(http=http.client).confirm(make_order(), signal) is None


async def test_confirm_rejects_a_usd_order() -> None:
    http = HttpRecorder(json_response(_status()))
    raw = _hook()
    signal = await _gateway(http=http.client).parse_webhook(
        webhook(raw, {"Signature": _sign("extra", raw)})
    )
    assert signal is not None

    order = make_order(currency=Currency.USD)
    assert await _gateway(http=http.client).confirm(order, signal) is None
