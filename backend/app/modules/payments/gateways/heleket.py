from app.modules.payments.gateways.cryptomus import CryptomusGateway


class HeleketGateway(CryptomusGateway):
    trusted_networks = ("31.133.220.8/32",)
    API_BASE = "https://api.heleket.com"
