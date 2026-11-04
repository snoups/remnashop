from typing import Optional

import pytest

from app.core.enums import TransactionStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.base import PaymentHttpClient
from app.modules.transactions.gateways.platega import PlategaGateway
from app.modules.users import UserDto
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

_SETTINGS = {"merchant_id": "m-1", "api_key": "secret"}
_HEADERS = {"X-MerchantId": "m-1", "X-Secret": "secret"}


def _gateway(
    *, http: PaymentHttpClient = NO_HTTP, customer: Optional[UserDto] = None
) -> PlategaGateway:
    return PlategaGateway(
        settings=_SETTINGS,
        webhook_url=WEBHOOK_URL,
        return_url=RETURN_URL,
        http=http,
        customer=customer,
    )


def _callback(status: str = "CONFIRMED") -> dict[str, object]:
    return {"id": "tx-1", "amount": 500.0, "currency": "RUB", "status": status, "paymentMethod": 2}


def _transaction(status: str = "CONFIRMED") -> dict[str, object]:
    return {
        "id": "tx-1",
        "status": status,
        "paymentDetails": {"amount": 500, "currency": "RUB"},
        "payload": ORDER_REF,
    }


async def test_create_payment_stores_the_transaction_id() -> None:
    http = HttpRecorder(
        json_response({"transactionId": "tx-1", "redirect": "https://pay/1", "status": "PENDING"}),
    )
    intent = await _gateway(http=http.client).create_payment(make_order())
    assert intent.provider_payment_id == "tx-1"
    assert intent.confirmation_url == "https://pay/1"


async def test_create_payment_sends_the_payer_id_as_metadata() -> None:
    http = HttpRecorder(
        json_response({"transactionId": "tx-1", "redirect": "https://pay/1"}),
    )
    await _gateway(http=http.client).create_payment(make_order())
    assert http.last_json()["metadata"] == {"userId": "7", "user_email": "7@mail.ru"}
    assert http.last_json()["payload"] == ORDER_REF


@pytest.mark.parametrize(
    ("email", "telegram_id", "expected"),
    [
        ("buyer@gmail.com", 5512345678, "buyer@gmail.com"),
        (None, 5512345678, "5512345678@telegram.org"),
        (None, None, "7@mail.ru"),
    ],
)
async def test_create_payment_identifies_the_buyer_by_one_email(
    email: Optional[str], telegram_id: Optional[int], expected: str
) -> None:
    http = HttpRecorder(
        json_response({"transactionId": "tx-1", "redirect": "https://pay/1"}),
    )
    customer = UserDto(id=7, name="buyer", email=email, telegram_id=telegram_id)
    await _gateway(http=http.client, customer=customer).create_payment(make_order())
    assert http.last_json()["metadata"]["user_email"] == expected


async def test_parse_webhook_checks_credentials() -> None:
    signal = await _gateway().parse_webhook(webhook(_callback(), _HEADERS))
    assert signal is not None and signal.claims_paid is True
    assert signal.provider_payment_id == "tx-1"

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(_callback(), {**_HEADERS, "X-Secret": "wrong"}))
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(_callback(), {**_HEADERS, "X-Secret": "секрет"}))
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(_callback()))


async def test_parse_webhook_canceled_does_not_claim_payment() -> None:
    signal = await _gateway().parse_webhook(webhook(_callback("CANCELED"), _HEADERS))
    assert signal is not None and signal.claims_paid is False


async def test_confirm_reads_the_transaction() -> None:
    http = HttpRecorder(json_response(_transaction()))
    signal = await _gateway(http=http.client).parse_webhook(webhook(_callback(), _HEADERS))
    assert signal is not None

    confirmed = await _gateway(http=http.client).confirm(
        make_order(external_payment_id="tx-1"), signal
    )

    assert confirmed is not None
    assert http.last.url.path == "/transaction/tx-1"
    assert http.last.headers["X-Secret"] == "secret"


async def test_confirm_rejects_a_pending_transaction() -> None:
    http = HttpRecorder(json_response(_transaction("PENDING")))
    signal = await _gateway(http=http.client).parse_webhook(webhook(_callback(), _HEADERS))
    assert signal is not None
    assert (
        await _gateway(http=http.client).confirm(make_order(external_payment_id="tx-1"), signal)
        is None
    )


async def test_parse_webhook_canceled_reports_canceled() -> None:
    signal = await _gateway().parse_webhook(webhook(_callback("CANCELED"), _HEADERS))
    assert signal is not None and signal.claims_paid is False
    assert signal.reported_status is TransactionStatus.CANCELED


async def test_parse_webhook_chargeback_reports_refunded() -> None:
    signal = await _gateway().parse_webhook(webhook(_callback("CHARGEBACKED"), _HEADERS))
    assert signal is not None and signal.claims_paid is False
    assert signal.reported_status is TransactionStatus.REFUNDED


async def test_confirm_rejects_a_transaction_of_another_order() -> None:
    http = HttpRecorder(json_response({**_transaction(), "payload": "other"}))
    signal = await _gateway(http=http.client).parse_webhook(webhook(_callback(), _HEADERS))
    assert signal is not None
    assert (
        await _gateway(http=http.client).confirm(make_order(external_payment_id="tx-1"), signal)
        is None
    )
