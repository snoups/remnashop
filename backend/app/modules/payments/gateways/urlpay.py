from app.modules.payments.gateways.mulenpay import MulenPayGateway


class UrlPayGateway(MulenPayGateway):
    API_BASE = "https://urlpay.io/api"
