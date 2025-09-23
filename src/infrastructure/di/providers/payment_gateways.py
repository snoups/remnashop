from __future__ import annotations

from typing import Type

from aiogram import Bot
from dishka import Provider, Scope, provide
from loguru import logger

from src.core.enums import PaymentGatewayType
from src.infrastructure.database.models.dto import PaymentGatewayDto
from src.infrastructure.payment_gateways import (
    BasePaymentGateway,
    PaymentGatewayFactory,
    TelegramStarsGateway,
    YookassaGateway,
)

GATEWAY_MAP: dict[PaymentGatewayType, Type[BasePaymentGateway]] = {
    PaymentGatewayType.TELEGRAM_STARS: TelegramStarsGateway,
    PaymentGatewayType.YOOKASSA: YookassaGateway,
    # PaymentGatewayType.YOOMONEY: YoomoneyGateway,
    # PaymentGatewayType.CRYPTOMUS: CryptomusGateway,
    # PaymentGatewayType.HELEKET: HeleketGateway,
}


class PaymentGatewaysProvider(Provider):
    scope = Scope.APP
    _cached_gateways: dict[PaymentGatewayType, BasePaymentGateway] = {}

    @provide()
    def get_gateway_factory(self, bot: Bot) -> PaymentGatewayFactory:
        def create_gateway(gateway: PaymentGatewayDto) -> BasePaymentGateway:
            gateway_type = gateway.type

            if gateway_type in self._cached_gateways:
                cached_gateway = self._cached_gateways[gateway_type]

                if cached_gateway.gateway != gateway:
                    logger.warning(
                        f"Gateway data for {gateway_type} has changed. Re-initializing the gateway"
                    )
                    del self._cached_gateways[gateway_type]

            if gateway_type not in self._cached_gateways:
                gateway_instance = GATEWAY_MAP.get(gateway_type)

                if not gateway_instance:
                    raise ValueError(f"Unknown gateway type: {gateway_type}")

                self._cached_gateways[gateway_type] = gateway_instance(gateway=gateway, bot=bot)
                logger.debug(f"Initialized new gateway instance for {gateway_type}")

            return self._cached_gateways[gateway_type]

        return create_gateway
