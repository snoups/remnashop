import pytest

from app.core.config import AppConfig
from app.core.enums import PaymentGatewayType
from app.core.exceptions import ValidationError
from app.modules.transactions import PaymentGatewayFactory
from app.modules.transactions.gateways.registry import GATEWAY_REGISTRY
from app.modules.transactions.gateways.yookassa import YooKassaGateway
from tests.modules.transactions.gateways.support import NO_HTTP


def test_build_returns_the_registered_adapter_wired_with_config(config: AppConfig) -> None:
    factory = PaymentGatewayFactory(config, NO_HTTP)
    gateway = factory.build(PaymentGatewayType.YOOKASSA, {"shop_id": "1", "api_key": "k"})

    assert isinstance(gateway, YooKassaGateway)
    assert gateway._webhook_url == config.get_webhook(PaymentGatewayType.YOOKASSA)
    assert gateway._return_url.startswith("https://")
    assert gateway._http is NO_HTTP


def test_build_rejects_an_unregistered_gateway(
    config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Every currently-defined PaymentGatewayType has an adapter -- remove
    # one to exercise the miss.
    monkeypatch.delitem(GATEWAY_REGISTRY, PaymentGatewayType.YOOKASSA)
    factory = PaymentGatewayFactory(config, NO_HTTP)
    with pytest.raises(ValidationError):
        factory.build(PaymentGatewayType.YOOKASSA, {})
