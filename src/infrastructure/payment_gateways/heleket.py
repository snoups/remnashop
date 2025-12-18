from aiogram import Bot

from src.core.config import AppConfig
from src.infrastructure.database.models.dto import HeleketGatewaySettingsDto, PaymentGatewayDto

from .cryptomus import CryptomusGateway


class HeleketGateway(CryptomusGateway):
    API_BASE: str = "https://api.heleket.com"

    def __init__(self, gateway: PaymentGatewayDto, bot: Bot, config: AppConfig) -> None:
        super().__init__(gateway, bot, config)

        if not isinstance(self.data.settings, HeleketGatewaySettingsDto):
            raise TypeError(
                f"Invalid settings type: expected {HeleketGatewaySettingsDto.__name__}, "
                f"got {type(self.data.settings).__name__}"
            )
