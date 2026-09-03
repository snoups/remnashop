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


def test_gateway_currency_reads_the_registry() -> None:
    assert gateway_currency(PaymentGatewayType.YOOKASSA) is Currency.RUB


def test_gateway_currency_covers_telegram_stars() -> None:
    assert gateway_currency(PaymentGatewayType.TELEGRAM_STARS) is Currency.XTR


def test_gateway_currency_raises_for_an_unimplemented_type() -> None:
    with pytest.raises(KeyError):
        gateway_currency(PaymentGatewayType.CRYPTOMUS)
