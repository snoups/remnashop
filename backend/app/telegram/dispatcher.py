from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram_dialog import BgManagerFactory, setup_dialogs
from loguru import logger

from app.core.config import AppConfig
from app.core.constants import TTL_7D
from app.core.json import decode, encode
from app.telegram.filters import setup_global_filters
from app.telegram.middlewares import setup_middlewares
from app.telegram.routers import setup_routers


def get_dispatcher(config: AppConfig) -> Dispatcher:
    # Without a TTL, FSM/dialog data for a user who abandons mid-flow sits in
    # Redis forever. Both are sliding: aiogram refreshes the TTL on every
    # write, so an active dialog never expires early.
    storage = RedisStorage.from_url(
        config.redis.dsn,
        state_ttl=TTL_7D,
        data_ttl=TTL_7D,
        json_loads=decode,
        json_dumps=encode,  # bytes, which redis-py accepts as is
    )
    dispatcher = Dispatcher(storage=storage, config=config)
    logger.info("Initialized Dispatcher with Redis storage")
    return dispatcher


def get_bg_manager_factory(dispatcher: Dispatcher) -> BgManagerFactory:
    bg_manager_factory = setup_dialogs(router=dispatcher)
    logger.info("Dispatcher dialogs configured")
    return bg_manager_factory


def setup_dispatcher(dispatcher: Dispatcher) -> None:
    setup_middlewares(dispatcher)
    setup_global_filters(dispatcher)
    setup_routers(dispatcher)
    logger.info("Dispatcher layers configured")
