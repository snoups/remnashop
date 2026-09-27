from app.core.enums import Currency
from app.modules.payments.gateways.riopay import RioPayGateway


# Docs: https://docs.panel.valutix.kz/
class ValutixGateway(RioPayGateway):
    currency = Currency.USD
    API_BASE = "https://api.panel.valutix.kz"
    TOKEN_SETTING = "api_key"
