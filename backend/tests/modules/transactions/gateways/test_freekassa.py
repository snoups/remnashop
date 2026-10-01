import hashlib
import hmac
from urllib.parse import urlencode

import pytest

import app.modules.transactions.gateways.freekassa as freekassa_module
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.gateways.freekassa import FreeKassaGateway
from tests.modules.transactions.gateways.support import (
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    install_http,
    json_response,
    make_order,
    webhook,
)

_SETTINGS = {
    "shop_id": "42",
    "api_key": "api-key",
    "secret_word_2": "word2",
    "payment_system_id": "4",
}


def _gateway(**overrides: str) -> FreeKassaGateway:
    settings = {**_SETTINGS, **overrides}
    return FreeKassaGateway(settings=settings, webhook_url=WEBHOOK_URL, return_url=RETURN_URL)


def _api_signature(params: dict[str, object]) -> str:
    joined = "|".join(str(value) for _, value in sorted(params.items()))
    return hmac.new(b"api-key", joined.encode(), hashlib.sha256).hexdigest()


def _notification(amount: str = "500", signed_amount: str = "500", merchant: str = "42") -> bytes:
    sign = hashlib.md5(f"{merchant}:{signed_amount}:word2:{ORDER_REF}".encode()).hexdigest()
    fields = {
        "MERCHANT_ID": merchant,
        "AMOUNT": amount,
        "intid": "777",
        "MERCHANT_ORDER_ID": ORDER_REF,
        "SIGN": sign,
    }
    return urlencode(fields).encode()


def _orders(*orders: dict[str, object]) -> dict[str, object]:
    return {"type": "success", "pages": 1, "orders": list(orders)}


_PAID_ORDER = {
    "merchant_order_id": ORDER_REF,
    "fk_order_id": 777,
    "amount": 500.0,
    "currency": "RUB",
    "status": 1,
}


async def _fake_server_ip(webhook_url: str) -> str:
    return "198.51.100.7"


async def test_server_ip_is_resolved_once_within_the_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _resolve(
        host: str, *args: object, **kwargs: object
    ) -> list[tuple[int, int, int, str, tuple[str, int]]]:
        calls.append(host)
        return [(2, 1, 6, "", ("198.51.100.9", 0))]

    freekassa_module._server_ip_cache.clear()
    monkeypatch.setattr(freekassa_module.socket, "getaddrinfo", _resolve)
    url = "https://cache-test.example/x"
    assert await freekassa_module._resolve_server_ip(url) == "198.51.100.9"
    assert await freekassa_module._resolve_server_ip(url) == "198.51.100.9"
    assert calls == ["cache-test.example"]
    freekassa_module._server_ip_cache.clear()


async def test_server_ip_falls_back_when_the_domain_does_not_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail(*args: object, **kwargs: object) -> None:
        raise OSError("no such host")

    monkeypatch.setattr(freekassa_module.socket, "getaddrinfo", _fail)
    assert await freekassa_module._resolve_server_ip("https://shop.example/x") == "127.0.0.1"


async def test_create_payment_never_signs_none(monkeypatch: pytest.MonkeyPatch) -> None:
    http = install_http(
        monkeypatch,
        freekassa_module,
        json_response({"type": "success", "orderId": 777, "location": "https://pay.fk/1"}),
    )
    monkeypatch.setattr(freekassa_module, "_resolve_server_ip", _fake_server_ip)

    intent = await _gateway().create_payment(make_order(customer_email=None))

    body = http.last_json()
    signature = body.pop("signature")
    assert None not in body.values()
    assert body["ip"] == "198.51.100.7"
    assert body["email"] == f"user_{ORDER_REF}@telegram.org"
    assert signature == _api_signature(body)
    assert intent.provider_payment_id == "777"


async def test_create_payment_prefers_the_order_email(monkeypatch: pytest.MonkeyPatch) -> None:
    http = install_http(
        monkeypatch,
        freekassa_module,
        json_response({"type": "success", "orderId": 1, "location": "https://pay.fk/1"}),
    )
    await _gateway().create_payment(make_order(customer_email="buyer@example.com"))
    assert http.last_json()["email"] == "buyer@example.com"


async def test_parse_webhook_verifies_sign_without_an_ip_check() -> None:
    gateway = _gateway()
    signal = await gateway.parse_webhook(webhook(_notification()))

    assert signal is not None and signal.claims_paid is True
    assert signal.reference == ORDER_REF
    assert signal.provider_payment_id == "777"
    assert gateway.webhook_ack(signal).body == "YES"


@pytest.mark.parametrize(
    "body",
    [
        _notification(amount="1", signed_amount="500"),
        _notification(merchant="43"),
    ],
)
async def test_parse_webhook_rejects_tampering(body: bytes) -> None:
    with pytest.raises(PaymentGatewayError):
        await _gateway().parse_webhook(webhook(body))


async def test_confirm_finds_the_order_by_payment_id(monkeypatch: pytest.MonkeyPatch) -> None:
    http = install_http(monkeypatch, freekassa_module, json_response(_orders(_PAID_ORDER)))
    signal = await _gateway().parse_webhook(webhook(_notification()))
    assert signal is not None

    confirmed = await _gateway().confirm(make_order(), signal)

    body = http.last_json()
    signature = body.pop("signature")
    assert confirmed is not None and confirmed.provider_payment_id == "777"
    assert http.last.url.path == "/v1/orders"
    assert body["paymentId"] == ORDER_REF
    assert signature == _api_signature(body)


@pytest.mark.parametrize(
    "orders",
    [
        [],
        [{**_PAID_ORDER, "status": 0}],
        [{**_PAID_ORDER, "merchant_order_id": "someone-else"}],
    ],
)
async def test_confirm_rejects_missing_or_unpaid_orders(
    monkeypatch: pytest.MonkeyPatch, orders: list[dict[str, object]]
) -> None:
    install_http(monkeypatch, freekassa_module, json_response(_orders(*orders)))
    signal = await _gateway().parse_webhook(webhook(_notification()))
    assert signal is not None
    assert await _gateway().confirm(make_order(), signal) is None
