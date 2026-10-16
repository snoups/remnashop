from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.telegram_stars import TelegramStarsGateway, stars_amount
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


def _gateway(recorder: HttpRecorder) -> TelegramStarsGateway:
    gateway = TelegramStarsGateway(
        settings={"bot_token": "TOKEN"},
        webhook_url=WEBHOOK_URL,
        return_url=RETURN_URL,
        http=NO_HTTP,
    )
    gateway._client = lambda: httpx.AsyncClient(  # type: ignore[method-assign]
        transport=httpx.MockTransport(recorder)
    )
    return gateway


def _order(final_price: str) -> Any:
    return make_order(currency=Currency.XTR, final_price=Decimal(final_price))


def test_stars_amount_rounds_up_to_whole_stars() -> None:
    assert stars_amount(_order("10.2")) == 11
    assert stars_amount(_order("10")) == 10


async def test_create_payment_returns_the_invoice_link() -> None:
    recorder = HttpRecorder(json_response({"ok": True, "result": "https://t.me/$abc"}))

    intent = await _gateway(recorder).create_payment(_order("50"))

    body = recorder.last_json()
    assert intent.confirmation_url == "https://t.me/$abc"
    assert str(recorder.last.url).endswith("/botTOKEN/createInvoiceLink")
    assert body["currency"] == "XTR"
    assert body["prices"] == [{"label": "XTR", "amount": 50}]
    assert body["payload"] == ORDER_REF


async def test_create_payment_raises_on_a_refusal() -> None:
    recorder = HttpRecorder(json_response({"ok": False, "description": "bad"}, 400))

    with pytest.raises(PaymentGatewayError) as raised:
        await _gateway(recorder).create_payment(_order("50"))

    assert "TOKEN" not in str(raised.value)


async def test_webhook_is_refused() -> None:
    with pytest.raises(PaymentGatewayError):
        await _gateway(HttpRecorder(json_response({}))).parse_webhook(webhook({}))
