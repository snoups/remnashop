import hashlib
from decimal import Decimal
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest

import app.modules.transactions.gateways.robokassa as robokassa_module
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.common import format_moscow
from app.modules.transactions.gateways.robokassa import RobokassaGateway
from tests.modules.transactions.gateways.support import (
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    install_http,
    make_order,
    webhook,
)

_SETTINGS = {"merchant_login": "shop", "password1": "p1", "password2": "p2"}
_XML = (
    '﻿<?xml version="1.0" encoding="utf-8"?>'
    '<OperationStateResponse xmlns="http://merchant.roboxchange.com/WebService/">'
    "<Result><Code>{result}</Code></Result>"
    "<State><Code>{state}</Code></State>"
    "<Info><OutCurrLabel>RUB</OutCurrLabel><OutSum>485.000000</OutSum></Info>"
    "<UserFields><Field><Name>shp_order_id</Name><Value>{order_ref}</Value></Field></UserFields>"
    "</OperationStateResponse>"
)


def _gateway() -> RobokassaGateway:
    return RobokassaGateway(settings=_SETTINGS, webhook_url=WEBHOOK_URL, return_url=RETURN_URL)


def _md5(message: str) -> str:
    return hashlib.md5(message.encode()).hexdigest()


def _result_url(out_sum: str = "500.000000", password: str = "p2") -> bytes:
    signature = _md5(f"{out_sum}:42:{password}:Shp_order_id={ORDER_REF}").upper()
    fields = {
        "OutSum": out_sum,
        "InvId": "42",
        "Fee": "15.000000",
        "SignatureValue": signature,
        "Shp_order_id": ORDER_REF,
    }
    return urlencode(fields).encode()


def _xml_response(result: int = 0, state: int = 100, order_ref: str = ORDER_REF) -> httpx.Response:
    body = _XML.format(result=result, state=state, order_ref=order_ref).encode("utf-8")
    return httpx.Response(200, content=body, headers={"content-type": "text/xml"})


async def test_create_payment_uses_the_order_id_and_expiry() -> None:
    order = make_order()

    intent = await _gateway().create_payment(order)

    assert intent.confirmation_url is not None
    params = {k: v[0] for k, v in parse_qs(urlsplit(intent.confirmation_url).query).items()}
    assert params["InvId"] == "42"
    assert params["SignatureValue"] == _md5(f"shop:500.00:42:p1:Shp_order_id={ORDER_REF}")
    assert params["ExpirationDate"] == format_moscow(order.expires_at)
    assert params["Shp_order_id"] == ORDER_REF
    assert intent.provider_payment_id == "42"


async def test_parse_webhook_verifies_password2_and_acks_with_inv_id() -> None:
    gateway = _gateway()
    signal = await gateway.parse_webhook(webhook(_result_url()))

    assert signal is not None and signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "42"
    assert signal.amount == Decimal("500")
    assert gateway.webhook_ack(signal).body == "OK42"


async def test_parse_webhook_rejects_a_password1_signature() -> None:
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(_result_url(password="p1")))


async def test_confirm_reads_op_state_ext(monkeypatch: pytest.MonkeyPatch) -> None:
    http = install_http(monkeypatch, robokassa_module, lambda request: _xml_response())
    signal = await _gateway().parse_webhook(webhook(_result_url()))
    assert signal is not None

    confirmed = await _gateway().confirm(make_order(), signal)

    assert confirmed is not None and confirmed.amount == Decimal("500")
    assert http.last.url.path.endswith("/OpStateExt")
    assert http.last.url.params["InvoiceID"] == "42"
    assert http.last.url.params["Signature"] == _md5("shop:42:p2")


@pytest.mark.parametrize(("result", "state"), [(0, 5), (0, 50), (3, 0)])
async def test_confirm_rejects_unfinished_or_unknown_operations(
    monkeypatch: pytest.MonkeyPatch, result: int, state: int
) -> None:
    install_http(monkeypatch, robokassa_module, lambda request: _xml_response(result, state))
    signal = await _gateway().parse_webhook(webhook(_result_url()))
    assert signal is not None
    assert await _gateway().confirm(make_order(), signal) is None


async def test_confirm_raises_on_op_state_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    install_http(monkeypatch, robokassa_module, lambda request: _xml_response(1, 0))
    signal = await _gateway().parse_webhook(webhook(_result_url()))
    assert signal is not None
    with pytest.raises(PaymentGatewayError):
        await _gateway().confirm(make_order(), signal)


async def test_confirm_rejects_an_invoice_of_another_order(monkeypatch: pytest.MonkeyPatch) -> None:
    install_http(monkeypatch, robokassa_module, lambda request: _xml_response(order_ref="other"))
    signal = await _gateway().parse_webhook(webhook(_result_url()))
    assert signal is not None
    assert await _gateway().confirm(make_order(), signal) is None
