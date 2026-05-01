from dishka import Provider
from dishka.integrations.aiogram import AiogramProvider

from .bot import BotProvider
from .config import ConfigProvider
from .dao import DaoProvider
from .database import DatabaseProvider
from .i18n import I18nAiogramProvider, I18nProvider, I18nTaskiqProvider
from .payment_gateways import PaymentGatewaysProvider
from .redis import RedisProvider
from .remnawave import RemnawaveProvider
from .retort import RetortProvider
from .services import ServicesProvider
from .use_cases import UseCasesProvider


def get_aiogram_providers(local: bool = False) -> list[Provider]:
    common = [
        AiogramProvider(),
        BotProvider(),
        ConfigProvider(),
        I18nProvider(),
        I18nAiogramProvider(),
        PaymentGatewaysProvider(),
        RedisProvider(),
        RetortProvider(),
        ServicesProvider(),
        UseCasesProvider(),
    ]

    if local:
        from src.infrastructure.local import (
            LocalDaoProvider,
            LocalDatabaseProvider,
            LocalRemnawaveProvider,
        )

        return [
            common[0],
            common[1],
            common[2],
            LocalDaoProvider(),
            LocalDatabaseProvider(),
            *common[3:7],
            LocalRemnawaveProvider(),
            *common[7:],
        ]

    return [
        common[0],
        common[1],
        common[2],
        DaoProvider(),
        DatabaseProvider(),
        *common[3:7],
        RemnawaveProvider(),
        *common[7:],
    ]


def get_taskiq_providers() -> list[Provider]:
    return [
        BotProvider(),
        ConfigProvider(),
        DaoProvider(),
        DatabaseProvider(),
        I18nProvider(),
        I18nTaskiqProvider(),
        PaymentGatewaysProvider(),
        RedisProvider(),
        RemnawaveProvider(),
        RetortProvider(),
        ServicesProvider(),
        UseCasesProvider(),
    ]
