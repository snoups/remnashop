from app.modules.payments.gateways.cryptomus import CryptomusGateway


# Docs: https://doc.heleket.com/
class HeleketGateway(CryptomusGateway):
    API_BASE = "https://api.heleket.com"
