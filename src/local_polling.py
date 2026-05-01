import asyncio

from dishka.integrations.aiogram import setup_dishka as setup_aiogram_dishka

from src.core.config import AppConfig
from src.core.logger import setup_logger
from src.infrastructure.di import create_aiogram_container
from src.infrastructure.services import EventBusImpl
from src.telegram.dispatcher import get_bg_manager_factory, get_dispatcher, setup_dispatcher


async def main() -> None:
    """
    Local entrypoint for running the full bot via long-polling (no webhook/domain required).
    Uses the same Dispatcher/routers/middlewares/DI as the production app.
    """

    config = AppConfig.get()
    setup_logger(config)

    dispatcher = get_dispatcher(config)
    bg_manager_factory = get_bg_manager_factory(dispatcher)
    setup_dispatcher(dispatcher)

    container = create_aiogram_container(config, bg_manager_factory)
    setup_aiogram_dishka(container, dispatcher, auto_inject=True)

    from aiogram import Bot  # local import keeps module dependencies simple

    bot: Bot = await container.get(Bot)
    event_bus = await container.get(EventBusImpl)
    event_bus.set_container_factory(lambda: container)
    event_bus.autodiscover()

    try:
        await dispatcher.start_polling(bot)
    finally:
        await event_bus.shutdown()
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
