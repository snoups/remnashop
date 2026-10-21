from app.modules.gateways import HeleketSettings
from app.modules.transactions.gateways.cryptomus import CryptomusGateway


# Docs: https://doc.heleket.com/
class HeleketGateway(CryptomusGateway):
    settings_model = HeleketSettings
    API_BASE = "https://api.heleket.com"
