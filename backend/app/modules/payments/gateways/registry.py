from typing import Final

from app.core.enums import Currency, PaymentGatewayType
from app.modules.payments.gateways.antilopay import AntilopayGateway
from app.modules.payments.gateways.aurapay import AuraPayGateway
from app.modules.payments.gateways.base import PaymentGateway
from app.modules.payments.gateways.cloudpayments import CloudPaymentsGateway
from app.modules.payments.gateways.cryptomus import CryptomusGateway
from app.modules.payments.gateways.cryptopay import CryptoPayGateway
from app.modules.payments.gateways.freekassa import FreeKassaGateway
from app.modules.payments.gateways.heleket import HeleketGateway
from app.modules.payments.gateways.lava import LavaGateway
from app.modules.payments.gateways.mulenpay import MulenPayGateway
from app.modules.payments.gateways.paymaster import PayMasterGateway
from app.modules.payments.gateways.paypalych import PaypalychGateway
from app.modules.payments.gateways.paypear import PayPearGateway
from app.modules.payments.gateways.platega import PlategaGateway
from app.modules.payments.gateways.riopay import RioPayGateway
from app.modules.payments.gateways.robokassa import RobokassaGateway
from app.modules.payments.gateways.rollypay import RollyPayGateway
from app.modules.payments.gateways.severpay import SeverPayGateway
from app.modules.payments.gateways.urlpay import UrlPayGateway
from app.modules.payments.gateways.valutix import ValutixGateway
from app.modules.payments.gateways.wata import WataGateway
from app.modules.payments.gateways.yookassa import YooKassaGateway
from app.modules.payments.gateways.yoomoney import YooMoneyGateway

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

# Gateways with no HTTP adapter (paid off-site, e.g. inside Telegram) still
# need a settlement currency for the checkout currency check.
NON_HTTP_GATEWAY_CURRENCIES: Final[dict[PaymentGatewayType, Currency]] = {
    PaymentGatewayType.TELEGRAM_STARS: Currency.XTR,
}


def gateway_currency(gateway_type: PaymentGatewayType, settings: dict[str, str]) -> Currency:
    if gateway_type not in GATEWAY_REGISTRY:
        return NON_HTTP_GATEWAY_CURRENCIES[gateway_type]

    # Admin-configured currency override, applies to any gateway whose settings
    # carry one -- validated at write time in UpdateGatewaySettingsUseCase, so
    # an invalid stored value here falls back to the class default rather than
    # breaking checkout.
    configured = settings.get("currency", "").strip()
    if configured:
        try:
            return Currency(configured.upper())
        except ValueError:
            pass
    return GATEWAY_REGISTRY[gateway_type].currency
