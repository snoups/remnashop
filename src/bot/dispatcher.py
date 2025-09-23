from aiogram import Dispatcher
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from aiogram_dialog import BgManagerFactory, setup_dialogs

from src.bot.filters import setup_global_filters
from src.bot.middlewares import setup_middlewares
from src.bot.routers import setup_error_handlers, setup_routers
from src.core.config import AppConfig
from src.core.utils import mjson


def create_dispatcher(config: AppConfig) -> Dispatcher:
    dispatcher = Dispatcher(
        storage=RedisStorage.from_url(
            url=config.redis.dsn,
            key_builder=DefaultKeyBuilder(
                with_bot_id=True,
                with_destiny=True,
            ),
            json_loads=mjson.decode,
            json_dumps=mjson.encode,
        ),
        config=config,  # for banners
    )

    return dispatcher


def create_bg_manager_factory(dispatcher: Dispatcher) -> BgManagerFactory:
    return setup_dialogs(router=dispatcher)


def setup_dispatcher(dispatcher: Dispatcher) -> None:
    # request -> outer middleware -> filter -> inner middleware -> handler #
    setup_middlewares(router=dispatcher)
    setup_global_filters(router=dispatcher)
    setup_routers(router=dispatcher)
    setup_error_handlers(router=dispatcher)
