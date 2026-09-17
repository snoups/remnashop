from app.modules.payments.gateways.cryptomus import CryptomusGateway


class HeleketGateway(CryptomusGateway):
    API_BASE = "https://api.heleket.com"
