from app.core.config import AppConfig
from app.core.enums import PaymentGatewayType
from app.core.exceptions import ValidationError
from app.modules.payments.gateways.base import PaymentGateway
from app.modules.payments.gateways.registry import GATEWAY_REGISTRY


class PaymentGatewayFactory:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def build(self, gateway_type: PaymentGatewayType, settings: dict[str, str]) -> PaymentGateway:
        gateway_class = GATEWAY_REGISTRY.get(gateway_type)
        if gateway_class is None:
            raise ValidationError(f"Gateway '{gateway_type.value}' has no implementation")
        return gateway_class(
            settings=settings,
            webhook_url=self._config.get_webhook(gateway_type),
            return_url=f"https://{self._config.domain.get_secret_value()}",
        )
