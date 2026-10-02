import base64
import hashlib
import json
from typing import Optional

import pytest

from app.core.enums import Currency, TransactionStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.dto import TransactionDto
from app.modules.transactions.gateways.base import PaymentHttpClient
from app.modules.transactions.gateways.cryptomus import CryptomusGateway
from app.modules.transactions.gateways.heleket import HeleketGateway
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

_SETTINGS = {"merchant_id": "m-1", "api_key": "key"}
_GATEWAYS = [(CryptomusGateway, "api.cryptomus.com"), (HeleketGateway, "api.heleket.com")]


def _gateway(
    cls: type[CryptomusGateway] = CryptomusGateway, *, http: PaymentHttpClient = NO_HTTP
) -> CryptomusGateway:
    return cls(settings=_SETTINGS, webhook_url=WEBHOOK_URL, return_url=RETURN_URL, http=http)


def _md5_sign(body: bytes) -> str:
    return hashlib.md5(base64.b64encode(body) + b"key").hexdigest()


def _hook(status: str = "paid") -> dict[str, object]:
    data: dict[str, object] = {
        "type": "payment",
        "uuid": "u-1",
        "order_id": ORDER_REF,
        "amount": "500.00",
        "status": status,
        "is_final": True,
        "additional_data": "Оплата https://shop.example/1",
        "txid": "a/b",
    }
    # json_encode($data, JSON_UNESCAPED_UNICODE): raw Cyrillic, escaped slashes.
    php_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("/", "\\/")
    return {**data, "sign": _md5_sign(php_json.encode())}


def _order() -> TransactionDto:
    return make_order(currency=Currency.USD)


@pytest.mark.parametrize(("cls", "host"), _GATEWAYS)
async def test_create_payment_signs_the_body_and_stores_the_uuid(
    cls: type[CryptomusGateway], host: str
) -> None:
    http = HttpRecorder(
        json_response({"state": 0, "result": {"uuid": "u-1", "url": "https://pay/1"}}),
    )

    intent = await _gateway(cls, http=http.client).create_payment(_order())

    assert http.last.url.host == host
    assert http.last.headers["sign"] == _md5_sign(http.last.content)
    assert 300 <= json.loads(http.last.content)["lifetime"] <= 1800
    assert intent.provider_payment_id == "u-1"


async def test_parse_webhook_accepts_the_php_signature() -> None:
    signal = await _gateway().parse_webhook(webhook(_hook()))

    assert signal is not None and signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "u-1"


async def test_parse_webhook_rejects_a_tampered_body() -> None:
    body = {**_hook(), "amount": "1.00"}
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(body))


@pytest.mark.parametrize(
    ("status", "claims", "reported_status"),
    [
        ("paid_over", True, None),
        ("check", False, None),
        ("cancel", False, TransactionStatus.CANCELED),
        ("fail", False, TransactionStatus.FAILED),
        ("system_fail", False, TransactionStatus.FAILED),
        ("wrong_amount", False, TransactionStatus.FAILED),
        ("refund_paid", False, TransactionStatus.REFUNDED),
    ],
)
async def test_parse_webhook_status_mapping(
    status: str, claims: bool, reported_status: Optional[TransactionStatus]
) -> None:
    signal = await _gateway().parse_webhook(webhook(_hook(status)))
    assert signal is not None and signal.claims_paid is claims
    assert signal.reported_status is reported_status


@pytest.mark.parametrize(("cls", "host"), _GATEWAYS)
async def test_confirm_queries_payment_info_by_order_id(
    cls: type[CryptomusGateway], host: str
) -> None:
    http = HttpRecorder(
        json_response(
            {
                "state": 0,
                "result": {
                    "uuid": "u-1",
                    "order_id": ORDER_REF,
                    "amount": "500.00",
                    "currency": "USD",
                    "status": "paid",
                },
            }
        ),
    )
    signal = await _gateway(cls, http=http.client).parse_webhook(webhook(_hook()))
    assert signal is not None

    confirmed = await _gateway(cls, http=http.client).confirm(_order(), signal)

    assert confirmed is not None
    assert http.last.url.host == host
    assert http.last.url.path == "/v1/payment/info"
    assert json.loads(http.last.content) == {"order_id": ORDER_REF}
    assert http.last.headers["sign"] == _md5_sign(http.last.content)


async def test_confirm_rejects_an_unpaid_invoice() -> None:
    http = HttpRecorder(
        json_response({"state": 0, "result": {"order_id": ORDER_REF, "status": "check"}}),
    )
    signal = await _gateway(http=http.client).parse_webhook(webhook(_hook()))
    assert signal is not None
    assert await _gateway(http=http.client).confirm(_order(), signal) is None
