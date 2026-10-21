from app.core.enums import Currency
from app.modules.gateways import ValutixSettings
from app.modules.transactions.gateways.riopay import RioPayGateway


# Docs: https://docs.panel.valutix.kz/
class ValutixGateway(RioPayGateway):
    settings_model = ValutixSettings
    currency = Currency.USD
    API_BASE = "https://api.panel.valutix.kz"
