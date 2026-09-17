import base64
import json
from typing import Final

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import app.modules.payments.gateways.antilopay as antilopay_module
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.gateways.antilopay import AntilopayGateway
from tests.modules.payments.gateways.support import (
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    install_http,
    json_response,
    make_order,
    webhook,
)

_MERCHANT_KEY: Final[rsa.RSAPrivateKey] = rsa.generate_private_key(
    public_exponent=65537, key_size=2048
)
_PROVIDER_KEY: Final[rsa.RSAPrivateKey] = rsa.generate_private_key(
    public_exponent=65537, key_size=2048
)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _settings(public_key_format: str = "der") -> dict[str, str]:
    public_key = _PROVIDER_KEY.public_key()
    if public_key_format == "der":
        encoded = _b64(
            public_key.public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )
    else:
        encoded = public_key.public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
    private_der = _MERCHANT_KEY.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return {
        "secret_id": "sid",
        "private_key": _b64(private_der),
        "public_key": encoded,
        "project_id": "P1",
    }


def _gateway(public_key_format: str = "der") -> AntilopayGateway:
    return AntilopayGateway(
        settings=_settings(public_key_format), webhook_url=WEBHOOK_URL, return_url=RETURN_URL
    )


def _provider_headers(body: bytes) -> dict[str, str]:
    signature = _PROVIDER_KEY.sign(body, padding.PKCS1v15(), hashes.SHA256())
    return {"X-Apay-Callback": _b64(signature), "X-Apay-Callback-Version": "1"}


def _assert_merchant_signed(body: bytes, signature: str) -> None:
    _MERCHANT_KEY.public_key().verify(
        base64.b64decode(signature), body, padding.PKCS1v15(), hashes.SHA256()
    )


def _callback(status: str = "SUCCESS", kind: str = "payment") -> bytes:
    return json.dumps(
        {
            "type": kind,
            "payment_id": "APAY1",
            "order_id": ORDER_REF,
            "amount": 490.0,
            "original_amount": 500.0,
            "fee": 10.0,
            "status": status,
            "currency": "RUB",
        }
    ).encode()


def _check(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "code": 0,
        "payment_id": "APAY1",
        "order_id": ORDER_REF,
        "amount": 490.0,
        "original_amount": 500.0,
        "status": "SUCCESS",
        "currency": "RUB",
    }
    body.update(overrides)
    return body


async def test_create_payment_posts_a_signed_body_to_api_v1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = install_http(
        monkeypatch,
        antilopay_module,
        json_response({"code": 0, "payment_id": "APAY1", "payment_url": "https://gate/1"}),
    )

    intent = await _gateway().create_payment(make_order())

    assert http.last.url.path == "/api/v1/payment/create"
    assert http.last.headers["X-Apay-Secret-Id"] == "sid"
    assert http.last.headers["X-Apay-Sign-Version"] == "1"
    _assert_merchant_signed(http.last.content, http.last.headers["X-Apay-Sign"])
    assert intent.provider_payment_id == "APAY1"


@pytest.mark.parametrize("key_format", ["der", "pem"])
async def test_parse_webhook_verifies_the_callback_signature(key_format: str) -> None:
    raw = _callback()
    signal = await _gateway(key_format).parse_webhook(webhook(raw, _provider_headers(raw)))

    assert signal is not None and signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "APAY1"


async def test_parse_webhook_rejects_missing_or_bad_signatures() -> None:
    raw = _callback()
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(raw))
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(raw, _provider_headers(b"other")))


async def test_parse_webhook_ignores_other_types_and_failures() -> None:
    refund = _callback(kind="refund")
    assert await _gateway().parse_webhook(webhook(refund, _provider_headers(refund))) is None
    failed = _callback("FAIL")
    signal = await _gateway().parse_webhook(webhook(failed, _provider_headers(failed)))
    assert signal is not None and signal.claims_paid is False


async def test_confirm_checks_the_payment_by_order_id(monkeypatch: pytest.MonkeyPatch) -> None:
    http = install_http(monkeypatch, antilopay_module, json_response(_check()))
    raw = _callback()
    signal = await _gateway().parse_webhook(webhook(raw, _provider_headers(raw)))
    assert signal is not None

    confirmed = await _gateway().confirm(make_order(), signal)

    assert confirmed is not None
    assert confirmed.amount == 500
    assert http.last.url.path == "/api/v1/payment/check"
    assert json.loads(http.last.content) == {"project_identificator": "P1", "order_id": ORDER_REF}
    _assert_merchant_signed(http.last.content, http.last.headers["X-Apay-Sign"])


@pytest.mark.parametrize(
    "response",
    [_check(original_amount=400.0), _check(status="PENDING"), {"code": 8, "error": "not found"}],
)
async def test_confirm_rejects_short_unpaid_or_unknown_payments(
    monkeypatch: pytest.MonkeyPatch, response: dict[str, object]
) -> None:
    install_http(monkeypatch, antilopay_module, json_response(response))
    raw = _callback()
    signal = await _gateway().parse_webhook(webhook(raw, _provider_headers(raw)))
    assert signal is not None
    assert await _gateway().confirm(make_order(), signal) is None


async def test_confirm_raises_on_api_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    install_http(monkeypatch, antilopay_module, json_response({"code": 3, "error": "bad sign"}))
    raw = _callback()
    signal = await _gateway().parse_webhook(webhook(raw, _provider_headers(raw)))
    assert signal is not None
    with pytest.raises(PaymentGatewayError):
        await _gateway().confirm(make_order(), signal)
