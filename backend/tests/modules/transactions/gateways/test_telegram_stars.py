from decimal import Decimal
from typing import Any

import pytest

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.core.telegram_api import BotApiRefusedError
from app.modules.transactions.gateways.telegram_stars import (
    TelegramStarsGateway,
    stars_amount,
    with_bot_settings,
)
from tests.fakes.telegram_bot import FakeBotSession, refusal, use_fake_bot
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


def _refused(description: str) -> BotApiRefusedError:
    return refusal(400, f"Bad Request: {description}")


def test_stars_amount_rounds_up_to_whole_stars() -> None:
    assert stars_amount(_order("10.2")) == 11
    assert stars_amount(_order("10")) == 10


async def test_create_payment_returns_the_invoice_link(monkeypatch: pytest.MonkeyPatch) -> None:
    session = use_fake_bot(monkeypatch, FakeBotSession({"createInvoiceLink": "https://t.me/$abc"}))

    intent = await _gateway().create_payment(_order("50"))

    assert intent.confirmation_url == "https://t.me/$abc"
    [call] = session.called("createInvoiceLink")
    assert (call["currency"], call["payload"]) == ("XTR", ORDER_REF)
    assert call["prices"] == [{"label": "XTR", "amount": 50}]
    assert session.proxy == "socks5://proxy:1080"


async def test_a_test_payment_invoice_names_no_term(monkeypatch: pytest.MonkeyPatch) -> None:
    # it buys nothing: its 0 days aren't "unlimited"
    session = use_fake_bot(monkeypatch, FakeBotSession({"createInvoiceLink": "https://t.me/$t"}))
    order = make_order(
        currency=Currency.XTR, final_price=Decimal("1"), duration_days=0, is_test=True
    )

    await _gateway().create_payment(order)

    [call] = session.called("createInvoiceLink")
    assert call["description"] == order.plan_snapshot.name


async def test_create_payment_raises_on_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    refused = _refused("bad")
    use_fake_bot(monkeypatch, FakeBotSession({"createInvoiceLink": lambda params: refused}))

    with pytest.raises(PaymentGatewayError) as raised:
        await _gateway().create_payment(_order("50"))

    assert _TOKEN not in str(raised.value)


async def test_refund_calls_refund_star_payment(monkeypatch: pytest.MonkeyPatch) -> None:
    session = use_fake_bot(monkeypatch, FakeBotSession({"refundStarPayment": True}))

    await _gateway().refund("charge-1", 42)

    [call] = session.called("refundStarPayment")
    assert (call["user_id"], call["telegram_payment_charge_id"]) == (42, "charge-1")


async def test_refund_of_an_already_refunded_charge_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refused = _refused("CHARGE_ALREADY_REFUNDED")
    use_fake_bot(monkeypatch, FakeBotSession({"refundStarPayment": lambda params: refused}))

    await _gateway().refund("charge-1", 42)


async def test_refund_refusal_raises_without_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    refused = _refused("CHARGE_NOT_FOUND")
    use_fake_bot(monkeypatch, FakeBotSession({"refundStarPayment": lambda params: refused}))

    with pytest.raises(PaymentGatewayError) as raised:
        await _gateway().refund("charge-1", 42)

    assert _TOKEN not in str(raised.value)
    assert raised.value.__cause__ is None


async def test_webhook_is_refused() -> None:
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook({}))
