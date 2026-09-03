import pytest

from app.core.enums import Currency, PaymentGatewayType
from app.modules.payments.gateways.base import PaymentGateway
from app.modules.payments.gateways.registry import (
    GATEWAY_REGISTRY,
    gateway_currency,
)


def test_every_registry_value_is_a_payment_gateway_with_a_currency() -> None:
    for gateway_type, cls in GATEWAY_REGISTRY.items():
        assert isinstance(gateway_type, PaymentGatewayType)
        assert issubclass(cls, PaymentGateway)
        assert isinstance(cls.currency, Currency)


def test_gateway_currency_reads_the_registry_by_default() -> None:
    assert gateway_currency(PaymentGatewayType.YOOKASSA, {}) is Currency.RUB


def test_gateway_currency_covers_telegram_stars() -> None:
    assert gateway_currency(PaymentGatewayType.TELEGRAM_STARS, {}) is Currency.XTR


def test_gateway_currency_raises_for_an_unimplemented_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Every currently-defined PaymentGatewayType has an adapter or a
    # NON_HTTP_GATEWAY_CURRENCIES entry -- remove one to exercise the miss.
    monkeypatch.delitem(GATEWAY_REGISTRY, PaymentGatewayType.YOOKASSA)
    with pytest.raises(KeyError):
        gateway_currency(PaymentGatewayType.YOOKASSA, {})


def test_gateway_currency_honors_an_admin_configured_override() -> None:
    assert GATEWAY_REGISTRY[PaymentGatewayType.CRYPTOMUS].currency is Currency.USD
    assert gateway_currency(PaymentGatewayType.CRYPTOMUS, {"currency": "RUB"}) is Currency.RUB


def test_gateway_currency_falls_back_on_an_invalid_stored_override() -> None:
    assert (
        gateway_currency(PaymentGatewayType.CRYPTOMUS, {"currency": "not-a-currency"})
        is Currency.USD
    )


def test_gateway_currency_ignores_a_blank_override() -> None:
    assert gateway_currency(PaymentGatewayType.CRYPTOMUS, {"currency": ""}) is Currency.USD
