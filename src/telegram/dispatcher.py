from datetime import timedelta

from aiogram import Dispatcher
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from aiogram_dialog import BgManagerFactory, setup_dialogs
from loguru import logger

from src.core.config import AppConfig
from src.infrastructure.common import json
from src.telegram.filters import setup_global_filters
from src.telegram.message_manager import MessageManager
from src.telegram.middlewares import setup_middlewares
from src.telegram.routers import setup_routers


def get_dispatcher(config: AppConfig) -> Dispatcher:
    storage = RedisStorage.from_url(
        url=config.redis.dsn,
        key_builder=DefaultKeyBuilder(
            with_bot_id=True,
            with_destiny=True,
        ),
        json_loads=json.decode,
        json_dumps=json.encode,
        state_ttl=timedelta(days=7),
        data_ttl=timedelta(days=7),
    )

    dispatcher = Dispatcher(storage=storage, config=config)
    logger.info("Initialized Dispatcher with Redis storage")
    return dispatcher


def get_dispatcher_preview() -> Dispatcher:
    return get_dispatcher(AppConfig())


def get_bg_manager_factory(dispatcher: Dispatcher) -> BgManagerFactory:
    bg_manager_factory = setup_dialogs(router=dispatcher, message_manager=MessageManager())
    logger.info("Dispatcher dialogs have been configured")
    return bg_manager_factory


def setup_dispatcher(dispatcher: Dispatcher) -> None:
    setup_middlewares(dispatcher)
    setup_global_filters(dispatcher)
    setup_routers(dispatcher)
    logger.info("Dispatcher layers have been configured")


def setup_worker_dispatcher(dispatcher: Dispatcher) -> None:
    setup_routers(dispatcher)
    logger.info("Worker dispatcher routers have been configured")
