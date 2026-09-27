from app.modules.payments.gateways.mulenpay import MulenPayGateway


# Docs: https://urlpay.io/docs/api
class UrlPayGateway(MulenPayGateway):
    API_BASE = "https://urlpay.io/api"
