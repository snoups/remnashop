from aiogram import Dispatcher
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from aiogram_dialog import BgManagerFactory, setup_dialogs
from loguru import logger

from src.bot.filters import setup_global_filters
from src.bot.middlewares import setup_middlewares
from src.bot.routers import setup_error_handlers, setup_routers
from src.core.config import AppConfig


def get_dispatcher(config: AppConfig) -> Dispatcher:
    storage = RedisStorage.from_url(
        url=config.redis.dsn,
        key_builder=DefaultKeyBuilder(
            with_bot_id=True,
            with_destiny=True,
        ),
    )

    dispatcher = Dispatcher(storage=storage)
    logger.info("Initialized Dispatcher with Redis storage")
    return dispatcher


def get_dispatcher_preview() -> Dispatcher:
    return get_dispatcher(AppConfig())


def get_bg_manager_factory(dispatcher: Dispatcher) -> BgManagerFactory:
    bg_manager_factory = setup_dialogs(router=dispatcher)
    logger.info("Dispatcher dialogs have been configured")
    return bg_manager_factory


def setup_dispatcher(dispatcher: Dispatcher) -> None:
    setup_middlewares(router=dispatcher)
    setup_global_filters(router=dispatcher)
    setup_routers(router=dispatcher)
    setup_error_handlers(router=dispatcher)
    logger.info("Dispatcher layers have been configured")
