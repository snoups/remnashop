from typing import Final

from app.core.enums import Currency, PaymentGatewayType
from app.modules.payments.gateways.base import PaymentGateway
from app.modules.payments.gateways.yookassa import YooKassaGateway
from app.modules.payments.gateways.yoomoney import YooMoneyGateway

GATEWAY_REGISTRY: Final[dict[PaymentGatewayType, type[PaymentGateway]]] = {
    PaymentGatewayType.YOOKASSA: YooKassaGateway,
    PaymentGatewayType.YOOMONEY: YooMoneyGateway,
}

# Gateways with no HTTP adapter (paid off-site, e.g. inside Telegram) still
# need a settlement currency for the checkout currency check.
NON_HTTP_GATEWAY_CURRENCIES: Final[dict[PaymentGatewayType, Currency]] = {
    PaymentGatewayType.TELEGRAM_STARS: Currency.XTR,
}


def gateway_currency(gateway_type: PaymentGatewayType) -> Currency:
    if gateway_type in GATEWAY_REGISTRY:
        return GATEWAY_REGISTRY[gateway_type].currency
    return NON_HTTP_GATEWAY_CURRENCIES[gateway_type]
