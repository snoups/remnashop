from dishka import AsyncContainer
from dishka.integrations.aiogram import setup_dishka as setup_aiogram_dishka
from dishka.integrations.taskiq import setup_dishka as setup_taskiq_dishka
from taskiq import TaskiqEvents, TaskiqState
from taskiq_redis import RedisStreamBroker

from src.application.common import EventSubscriber
from src.core.config import AppConfig
from src.core.logger import setup_logger
from src.infrastructure.di import create_taskiq_container
from src.telegram.dispatcher import get_bg_manager_factory, get_dispatcher, setup_dispatcher

from .broker import broker


def worker() -> RedisStreamBroker:
    setup_logger(AppConfig.get())

    config = AppConfig.get()
    dispatcher = get_dispatcher(config)
    bg_manager_factory = get_bg_manager_factory(dispatcher)

    setup_dispatcher(dispatcher)

    container = create_taskiq_container(config, bg_manager_factory)
    broker.add_dependency_context({AsyncContainer: container})

    setup_taskiq_dishka(container, broker)
    setup_aiogram_dishka(container, dispatcher, auto_inject=True)

    @broker.on_event(TaskiqEvents.WORKER_STARTUP)
    async def startup(state: TaskiqState) -> None:
        event_bus = await container.get(EventSubscriber)
        event_bus.set_container_factory(lambda: container)
        event_bus.autodiscover()

    @broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
    async def shutdown(state: TaskiqState) -> None:
        event_bus = await container.get(EventSubscriber)
        await event_bus.shutdown()

    return broker
