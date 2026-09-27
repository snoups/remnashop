import hashlib
import hmac
import json
from typing import Any

import pytest

import app.modules.payments.gateways.severpay as severpay_module
from app.core.enums import PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.gateways.severpay import SeverPayGateway
from tests.modules.payments.gateways.support import (
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    install_http,
    json_response,
    make_order,
    webhook,
)

_SETTINGS = {"mid": "1", "token": "tok"}


def _gateway() -> SeverPayGateway:
    return SeverPayGateway(settings=_SETTINGS, webhook_url=WEBHOOK_URL, return_url=RETURN_URL)


def _hmac(body: bytes) -> str:
    return hmac.new(b"tok", body, hashlib.sha256).hexdigest()


def _assert_signed_request(payload: dict[str, Any]) -> None:
    sign = payload.pop("sign")
    ordered = dict(sorted(payload.items()))
    body = json.dumps(ordered, ensure_ascii=False, separators=(",", ":")).encode()
    assert sign == _hmac(body)
    assert payload["mid"] == 1
    assert payload["salt"]


def _hook(status: str = "success", *, php_escaped: bool = True, kind: str = "payin") -> bytes:
    data = {
        "type": kind,
        "data": {
            "id": 123,
            "order_id": ORDER_REF,
            "amount": 500.0,
            "currency": "RUB",
            "status": status,
            "note": "Оплата https://shop.example/1",
        },
        "salt": "a9f3c2d8e4b1",
    }
    if php_escaped:
        signed = json.dumps(data, separators=(",", ":")).replace("/", "\\/")
    else:
        signed = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return json.dumps({**data, "sign": _hmac(signed.encode())}).encode()


def _payin(status: str = "success") -> dict[str, object]:
    return {
        "status": True,
        "msg": "",
        "data": {
            "id": 123,
            "uid": "U1",
            "order_id": ORDER_REF,
            "amount": 500.0,
            "currency": "RUB",
            "status": status,
        },
    }


async def test_create_payment_signs_sorted_body_with_lifetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = install_http(
        monkeypatch,
        severpay_module,
        json_response({"status": True, "msg": "", "data": {"id": 123, "url": "https://sp/1"}}),
    )

    intent = await _gateway().create_payment(make_order())

    payload = http.last_json()
    assert payload["lifetime"] == 30
    assert payload["order_id"] == ORDER_REF
    _assert_signed_request(payload)
    assert intent.provider_payment_id == "123"


@pytest.mark.parametrize("php_escaped", [True, False])
async def test_parse_webhook_accepts_both_documented_encodings(php_escaped: bool) -> None:
    signal = await _gateway().parse_webhook(webhook(_hook(php_escaped=php_escaped)))

    assert signal is not None and signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "123"


async def test_parse_webhook_rejects_a_tampered_body() -> None:
    body = json.loads(_hook())
    body["data"]["amount"] = 1.0
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(body))


async def test_parse_webhook_test_notification_is_ignored_and_fail_does_not_claim() -> None:
    assert await _gateway().parse_webhook(webhook(_hook(kind="test"))) is None
    failed = await _gateway().parse_webhook(webhook(_hook("fail")))
    assert failed is not None and failed.claims_paid is False
    assert failed.reported_status is PaymentOrderStatus.FAILED
    declined = await _gateway().parse_webhook(webhook(_hook("decline")))
    assert declined is not None and declined.reported_status is PaymentOrderStatus.FAILED


def test_ack_is_the_documented_json() -> None:
    ack = _gateway().webhook_ack(None)
    assert json.loads(ack.body) == {"status": True}
    assert ack.media_type == "application/json"


async def test_confirm_reads_a_signed_payin_get(monkeypatch: pytest.MonkeyPatch) -> None:
    http = install_http(monkeypatch, severpay_module, json_response(_payin()))
    signal = await _gateway().parse_webhook(webhook(_hook()))
    assert signal is not None

    confirmed = await _gateway().confirm(make_order(external_payment_id="123"), signal)

    payload = http.last_json()
    assert confirmed is not None
    assert http.last.url.path == "/api/merchant/payin/get"
    assert payload["id"] == 123
    _assert_signed_request(payload)


@pytest.mark.parametrize(
    "response",
    [_payin("process"), {"status": False, "msg": "not found"}],
)
async def test_confirm_rejects_unfinished_or_unknown_payins(
    monkeypatch: pytest.MonkeyPatch, response: dict[str, object]
) -> None:
    install_http(monkeypatch, severpay_module, json_response(response))
    signal = await _gateway().parse_webhook(webhook(_hook()))
    assert signal is not None
    assert await _gateway().confirm(make_order(external_payment_id="123"), signal) is None
