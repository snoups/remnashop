import base64
import json
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Final

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import app.modules.payments.gateways.wata as wata_module
from app.core.enums import PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.core.utils.time import datetime_now
from app.modules.payments.gateways.wata import WataGateway, clear_public_key_cache
from tests.modules.payments.gateways.support import (
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    HttpRecorder,
    install_http,
    make_order,
    webhook,
)

_PROVIDER_KEY: Final[rsa.RSAPrivateKey] = rsa.generate_private_key(
    public_exponent=65537, key_size=2048
)
_PUBLIC_PEM: Final[str] = (
    _PROVIDER_KEY.public_key()
    .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    .decode()
)


@pytest.fixture(autouse=True)
def _fresh_key_cache() -> Iterator[None]:
    clear_public_key_cache()
    yield
    clear_public_key_cache()


def _gateway() -> WataGateway:
    return WataGateway(settings={"api_key": "tok"}, webhook_url=WEBHOOK_URL, return_url=RETURN_URL)


def _transaction(**overrides: object) -> dict[str, object]:
    transaction: dict[str, object] = {
        "id": "tx-1",
        "kind": "Payment",
        "status": "Paid",
        "amount": 500.0,
        "currency": "RUB",
        "orderId": ORDER_REF,
    }
    transaction.update(overrides)
    return transaction


def _install(monkeypatch: pytest.MonkeyPatch, transaction: dict[str, object]) -> HttpRecorder:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/public-key"):
            return httpx.Response(200, json={"value": _PUBLIC_PEM})
        if request.url.path.endswith("/links"):
            return httpx.Response(200, json={"id": "link-1", "url": "https://wata/1"})
        return httpx.Response(200, json=transaction)

    return install_http(monkeypatch, wata_module, respond)


def _signed(kind: str = "Payment", status: str = "Paid") -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(
        {
            "transactionType": "SBP",
            "kind": kind,
            "id": "tx-1",
            "transactionId": "refund-1",
            "paymentLinkId": "link-1",
            "transactionStatus": status,
            "amount": 500.0,
            "currency": "RUB",
            "orderId": ORDER_REF,
        }
    ).encode()
    signature = _PROVIDER_KEY.sign(raw, padding.PKCS1v15(), hashes.SHA512())
    return raw, {"X-Signature": base64.b64encode(signature).decode()}


async def test_create_payment_sets_an_expiry_past_the_provider_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = _install(monkeypatch, _transaction())

    intent = await _gateway().create_payment(make_order())

    body = http.last_json()
    expiry = datetime.fromisoformat(body["expirationDateTime"].replace("Z", "+00:00"))
    assert expiry >= datetime_now() + timedelta(minutes=29)
    assert body["orderId"] == ORDER_REF
    assert intent.confirmation_url == "https://wata/1"


async def test_parse_webhook_verifies_rsa_sha512(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _transaction())
    raw, headers = _signed()

    signal = await _gateway().parse_webhook(webhook(raw, headers))

    assert signal is not None and signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "tx-1"

    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(raw + b" ", headers))


async def test_parse_webhook_falls_back_to_transaction_id_without_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, _transaction())
    raw = json.dumps(
        {
            "kind": "Payment",
            "transactionId": "tx-9",
            "transactionStatus": "Paid",
            "orderId": ORDER_REF,
        }
    ).encode()
    signature = _PROVIDER_KEY.sign(raw, padding.PKCS1v15(), hashes.SHA512())
    headers = {"X-Signature": base64.b64encode(signature).decode()}

    signal = await _gateway().parse_webhook(webhook(raw, headers))

    assert signal is not None and signal.provider_payment_id == "tx-9"


async def test_parse_webhook_refund_with_paid_status_does_not_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, _transaction())
    raw, headers = _signed(kind="Refund")
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None and signal.claims_paid is False
    assert signal.reported_status is PaymentOrderStatus.REFUNDED


async def test_parse_webhook_declined_payment_reports_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, _transaction())
    raw, headers = _signed(status="Declined")
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None and signal.claims_paid is False
    assert signal.reported_status is PaymentOrderStatus.FAILED


async def test_confirm_reads_the_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    http = _install(monkeypatch, _transaction())
    raw, headers = _signed()
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None

    confirmed = await _gateway().confirm(make_order(), signal)

    assert confirmed is not None and confirmed.provider_payment_id == "tx-1"
    assert http.last.url.path == "/api/h2h/transactions/tx-1"


@pytest.mark.parametrize(
    "transaction",
    [
        _transaction(status="Declined"),
        _transaction(kind="Refund"),
        _transaction(orderId="someone-else"),
    ],
)
async def test_confirm_rejects_unpaid_refund_or_foreign_transactions(
    monkeypatch: pytest.MonkeyPatch, transaction: dict[str, object]
) -> None:
    _install(monkeypatch, transaction)
    raw, headers = _signed()
    signal = await _gateway().parse_webhook(webhook(raw, headers))
    assert signal is not None
    assert await _gateway().confirm(make_order(), signal) is None
