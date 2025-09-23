from dishka import Provider
from dishka.integrations.aiogram import AiogramProvider

from .bot import BotProvider
from .config import ConfigProvider
from .database import DatabaseProvider
from .i18n import I18nProvider
from .payment_gateways import PaymentGatewaysProvider
from .redis import RedisProvider
from .remnawave import RemnawaveProvider
from .services import ServicesProvider


def get_providers() -> list[Provider]:
    return [
        AiogramProvider(),
        BotProvider(),
        ConfigProvider(),
        DatabaseProvider(),
        I18nProvider(),
        RedisProvider(),
        RemnawaveProvider(),
        ServicesProvider(),
        PaymentGatewaysProvider(),
    ]
