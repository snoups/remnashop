import hashlib
import hmac
import json
from typing import Any

import pytest

import app.modules.transactions.gateways.aurapay as aurapay_module
from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.aurapay import AuraPayGateway
from tests.modules.transactions.gateways.support import (
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    install_http,
    json_response,
    make_order,
    webhook,
)

_SETTINGS = {"api_key": "key", "shop_id": "shop-1", "secret_key": "secret2"}


def _gateway() -> AuraPayGateway:
    return AuraPayGateway(settings=_SETTINGS, webhook_url=WEBHOOK_URL, return_url=RETURN_URL)


def _docs_signature(params: dict[str, Any]) -> str:
    ordered = dict(sorted(params.items()))
    concatenated = "".join("" if v is None else str(v) for v in ordered.values())
    return hmac.new(b"secret2", concatenated.encode(), hashlib.sha256).hexdigest()


def _hook(status: str = "PAID") -> dict[str, Any]:
    return {
        "id": "inv-1",
        "amount": "500.00",
        "status": status,
        "comment": "Order #42",
        "service": "sbp",
        "shop_id": "shop-1",
        "order_id": ORDER_REF,
        "custom_fields": None,
    }


async def test_create_payment_sends_lifetime_in_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    http = install_http(
        monkeypatch,
        aurapay_module,
        json_response({"id": "inv-1", "payment_data": {"url": "https://aura/1"}}),
    )

    intent = await _gateway().create_payment(make_order())

    body = http.last_json()
    assert 1 <= body["lifetime"] <= 30
    assert body["order_id"] == ORDER_REF
    assert http.last.headers["X-ShopId"] == "shop-1"
    assert intent.provider_payment_id == "inv-1"


async def test_parse_webhook_matches_the_docs_signature() -> None:
    body = _hook()
    signal = await _gateway().parse_webhook(
        webhook(json.dumps(body).encode(), {"X-SIGNATURE": _docs_signature(body)})
    )

    assert signal is not None and signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "inv-1"


async def test_parse_webhook_rejects_tampering_and_ignores_unpaid() -> None:
    body = _hook()
    tampered = {**body, "amount": "1.00"}
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(
            webhook(json.dumps(tampered).encode(), {"X-SIGNATURE": _docs_signature(body)})
        )
    expired = _hook("EXPIRED")
    signal = await _gateway().parse_webhook(
        webhook(json.dumps(expired).encode(), {"X-SIGNATURE": _docs_signature(expired)})
    )
    assert signal is not None and signal.claims_paid is False


async def test_confirm_reads_invoice_status(monkeypatch: pytest.MonkeyPatch) -> None:
    http = install_http(
        monkeypatch,
        aurapay_module,
        json_response({"id": "inv-1", "order_id": ORDER_REF, "amount": 500, "status": "PAID"}),
    )
    body = _hook()
    signal = await _gateway().parse_webhook(
        webhook(json.dumps(body).encode(), {"X-SIGNATURE": _docs_signature(body)})
    )
    assert signal is not None

    confirmed = await _gateway().confirm(make_order(external_payment_id="inv-1"), signal)

    assert confirmed is not None
    assert http.last.url.path == "/invoice/status"
    assert http.last_json() == {"id": "inv-1"}


async def test_confirm_rejects_a_pending_invoice(monkeypatch: pytest.MonkeyPatch) -> None:
    install_http(
        monkeypatch,
        aurapay_module,
        json_response({"id": "inv-1", "order_id": ORDER_REF, "amount": 500, "status": "PENDING"}),
    )
    body = _hook()
    signal = await _gateway().parse_webhook(
        webhook(json.dumps(body).encode(), {"X-SIGNATURE": _docs_signature(body)})
    )
    assert signal is not None
    assert await _gateway().confirm(make_order(external_payment_id="inv-1"), signal) is None


async def test_confirm_rejects_a_usd_order(monkeypatch: pytest.MonkeyPatch) -> None:
    install_http(
        monkeypatch,
        aurapay_module,
        json_response({"id": "inv-1", "order_id": ORDER_REF, "amount": 500, "status": "PAID"}),
    )
    body = _hook()
    signal = await _gateway().parse_webhook(
        webhook(json.dumps(body).encode(), {"X-SIGNATURE": _docs_signature(body)})
    )
    assert signal is not None

    order = make_order(external_payment_id="inv-1", currency=Currency.USD)
    assert await _gateway().confirm(order, signal) is None
