from app.modules.gateways import UrlPaySettings
from app.modules.transactions.gateways.mulenpay import MulenPayGateway


# Docs: https://urlpay.io/docs/api
class UrlPayGateway(MulenPayGateway):
    settings_model = UrlPaySettings
    API_BASE = "https://urlpay.io/api"
