from typing import Final

from app.core.enums import Currency, PaymentGatewayType
from app.modules.transactions.gateways.antilopay import AntilopayGateway
from app.modules.transactions.gateways.aurapay import AuraPayGateway
from app.modules.transactions.gateways.base import PaymentGateway
from app.modules.transactions.gateways.cloudpayments import CloudPaymentsGateway
from app.modules.transactions.gateways.cryptomus import CryptomusGateway
from app.modules.transactions.gateways.cryptopay import CryptoPayGateway
from app.modules.transactions.gateways.freekassa import FreeKassaGateway
from app.modules.transactions.gateways.heleket import HeleketGateway
from app.modules.transactions.gateways.lava import LavaGateway
from app.modules.transactions.gateways.mulenpay import MulenPayGateway
from app.modules.transactions.gateways.paymaster import PayMasterGateway
from app.modules.transactions.gateways.paypalych import PaypalychGateway
from app.modules.transactions.gateways.paypear import PayPearGateway
from app.modules.transactions.gateways.platega import PlategaGateway
from app.modules.transactions.gateways.riopay import RioPayGateway
from app.modules.transactions.gateways.robokassa import RobokassaGateway
from app.modules.transactions.gateways.rollypay import RollyPayGateway
from app.modules.transactions.gateways.severpay import SeverPayGateway
from app.modules.transactions.gateways.urlpay import UrlPayGateway
from app.modules.transactions.gateways.valutix import ValutixGateway
from app.modules.transactions.gateways.wata import WataGateway
from app.modules.transactions.gateways.yookassa import YooKassaGateway
from app.modules.transactions.gateways.yoomoney import YooMoneyGateway

GATEWAY_REGISTRY: Final[dict[PaymentGatewayType, type[PaymentGateway]]] = {
    PaymentGatewayType.YOOKASSA: YooKassaGateway,
    PaymentGatewayType.YOOMONEY: YooMoneyGateway,
    PaymentGatewayType.ROBOKASSA: RobokassaGateway,
    PaymentGatewayType.FREEKASSA: FreeKassaGateway,
    PaymentGatewayType.MULENPAY: MulenPayGateway,
    PaymentGatewayType.URLPAY: UrlPayGateway,
    PaymentGatewayType.PLATEGA: PlategaGateway,
    PaymentGatewayType.PAYMASTER: PayMasterGateway,
    PaymentGatewayType.CRYPTOMUS: CryptomusGateway,
    PaymentGatewayType.HELEKET: HeleketGateway,
    PaymentGatewayType.CRYPTOPAY: CryptoPayGateway,
    PaymentGatewayType.WATA: WataGateway,
    PaymentGatewayType.VALUTIX: ValutixGateway,
    PaymentGatewayType.ROLLYPAY: RollyPayGateway,
    PaymentGatewayType.ANTILOPAY: AntilopayGateway,
    PaymentGatewayType.AURAPAY: AuraPayGateway,
    PaymentGatewayType.RIOPAY: RioPayGateway,
    PaymentGatewayType.SEVERPAY: SeverPayGateway,
    PaymentGatewayType.PAYPEAR: PayPearGateway,
    PaymentGatewayType.LAVA: LavaGateway,
    PaymentGatewayType.CLOUDPAYMENTS: CloudPaymentsGateway,
    PaymentGatewayType.PAYPALYCH: PaypalychGateway,
}

# TELEGRAM_STARS docs: https://core.telegram.org/bots/payments-stars
# Gateways with no HTTP adapter (paid off-site, e.g. inside Telegram) still
# need a settlement currency for the checkout currency check.
NON_HTTP_GATEWAY_CURRENCIES: Final[dict[PaymentGatewayType, Currency]] = {
    PaymentGatewayType.TELEGRAM_STARS: Currency.XTR,
}


def gateway_currency(gateway_type: PaymentGatewayType, settings: dict[str, str]) -> Currency:
    if gateway_type not in GATEWAY_REGISTRY:
        return NON_HTTP_GATEWAY_CURRENCIES[gateway_type]

    # admin-set currency override, validated in UpdateGatewaySettingsUseCase;
    # an invalid stored value falls back to the class default
    configured = settings.get("currency", "").strip()
    if configured:
        try:
            return Currency(configured.upper())
        except ValueError:
            pass
    return GATEWAY_REGISTRY[gateway_type].currency
