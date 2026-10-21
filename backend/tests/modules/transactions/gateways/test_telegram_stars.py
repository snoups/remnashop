from decimal import Decimal
from typing import Any

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import CreateInvoiceLink, RefundStarPayment

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.telegram_stars import (
    TelegramStarsGateway,
    stars_amount,
    with_bot_settings,
)
from tests.fakes.telegram_bot import FakeBotSession, use_fake_bot
from tests.modules.transactions.gateways.support import (
    NO_HTTP,
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    make_order,
    webhook,
)

_TOKEN = "123:TOKEN"


def _gateway() -> TelegramStarsGateway:
    return TelegramStarsGateway(
        settings=with_bot_settings({}, _TOKEN, "socks5://proxy:1080"),
        webhook_url=WEBHOOK_URL,
        return_url=RETURN_URL,
        http=NO_HTTP,
    )


def _order(final_price: str) -> Any:
    return make_order(currency=Currency.XTR, final_price=Decimal(final_price))


def _refused(method: Any, description: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=method, message=f"Bad Request: {description}")


def test_stars_amount_rounds_up_to_whole_stars() -> None:
    assert stars_amount(_order("10.2")) == 11
    assert stars_amount(_order("10")) == 10


async def test_create_payment_returns_the_invoice_link(monkeypatch: pytest.MonkeyPatch) -> None:
    session = use_fake_bot(monkeypatch, FakeBotSession({"CreateInvoiceLink": "https://t.me/$abc"}))

    intent = await _gateway().create_payment(_order("50"))

    assert intent.confirmation_url == "https://t.me/$abc"
    [call] = session.called("CreateInvoiceLink")
    assert isinstance(call, CreateInvoiceLink)
    assert (call.currency, call.payload) == ("XTR", ORDER_REF)
    assert [(p.label, p.amount) for p in call.prices] == [("XTR", 50)]
    assert session.proxy == "socks5://proxy:1080"


async def test_create_payment_raises_on_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    refusal = _refused(CreateInvoiceLink, "bad")
    use_fake_bot(monkeypatch, FakeBotSession({"CreateInvoiceLink": lambda method: refusal}))

    with pytest.raises(PaymentGatewayError) as raised:
        await _gateway().create_payment(_order("50"))

    assert _TOKEN not in str(raised.value)


async def test_refund_calls_refund_star_payment(monkeypatch: pytest.MonkeyPatch) -> None:
    session = use_fake_bot(monkeypatch, FakeBotSession({"RefundStarPayment": True}))

    await _gateway().refund("charge-1", 42)

    [call] = session.called("RefundStarPayment")
    assert isinstance(call, RefundStarPayment)
    assert (call.user_id, call.telegram_payment_charge_id) == (42, "charge-1")


async def test_refund_of_an_already_refunded_charge_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refusal = _refused(RefundStarPayment, "CHARGE_ALREADY_REFUNDED")
    use_fake_bot(monkeypatch, FakeBotSession({"RefundStarPayment": lambda method: refusal}))

    await _gateway().refund("charge-1", 42)


async def test_refund_refusal_raises_without_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    refusal = _refused(RefundStarPayment, "CHARGE_NOT_FOUND")
    use_fake_bot(monkeypatch, FakeBotSession({"RefundStarPayment": lambda method: refusal}))

    with pytest.raises(PaymentGatewayError) as raised:
        await _gateway().refund("charge-1", 42)

    assert _TOKEN not in str(raised.value)
    assert raised.value.__cause__ is None


async def test_webhook_is_refused() -> None:
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook({}))
