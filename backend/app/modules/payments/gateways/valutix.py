from app.core.enums import Currency
from app.modules.payments.gateways.riopay import RioPayGateway


class ValutixGateway(RioPayGateway):
    currency = Currency.USD
    API_BASE = "https://api.panel.valutix.kz"
    TOKEN_SETTING = "api_key"
