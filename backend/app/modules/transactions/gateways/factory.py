from app.core.config import AppConfig
from app.core.enums import PaymentGatewayType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.transactions.gateways.base import PaymentGateway, PaymentHttpClient
from app.modules.transactions.gateways.registry import GATEWAY_REGISTRY


class PaymentGatewayFactory:
    def __init__(self, config: AppConfig, http: PaymentHttpClient) -> None:
        self._config = config
        self._http = http

    def build(self, gateway_type: PaymentGatewayType, settings: dict[str, str]) -> PaymentGateway:
        gateway_class = GATEWAY_REGISTRY.get(gateway_type)
        if gateway_class is None:
            raise ValidationError(
                f"Gateway '{gateway_type.value}' has no implementation",
                code=ErrorCode.GATEWAY_NOT_IMPLEMENTED,
            )
        return gateway_class(
            settings=settings,
            webhook_url=self._config.get_webhook(gateway_type),
            return_url=f"https://{self._config.domain.get_secret_value()}",
            http=self._http,
        )
