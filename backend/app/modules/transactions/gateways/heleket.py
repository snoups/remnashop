from app.modules.transactions.gateways.cryptomus import CryptomusGateway


# Docs: https://doc.heleket.com/
class HeleketGateway(CryptomusGateway):
    API_BASE = "https://api.heleket.com"
