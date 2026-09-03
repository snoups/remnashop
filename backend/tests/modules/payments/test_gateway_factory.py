import pytest

from app.core.config import AppConfig
from app.core.enums import PaymentGatewayType
from app.core.exceptions import ValidationError
from app.modules.payments import PaymentGatewayFactory
from app.modules.payments.gateways.yookassa import YooKassaGateway


def test_build_returns_the_registered_adapter_wired_with_config(config: AppConfig) -> None:
    factory = PaymentGatewayFactory(config)
    gateway = factory.build(PaymentGatewayType.YOOKASSA, {"shop_id": "1", "api_key": "k"})

    assert isinstance(gateway, YooKassaGateway)
    assert gateway._webhook_url == config.get_webhook(PaymentGatewayType.YOOKASSA)
    assert gateway._return_url.startswith("https://")


def test_build_rejects_an_unregistered_gateway(config: AppConfig) -> None:
    factory = PaymentGatewayFactory(config)
    with pytest.raises(ValidationError):
        factory.build(PaymentGatewayType.CRYPTOMUS, {})
