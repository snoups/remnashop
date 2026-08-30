from dishka import AsyncContainer
from dishka.integrations.taskiq import setup_dishka
from taskiq import TaskiqEvents, TaskiqState

from app.core.config import AppConfig
from app.worker.broker import broker
from app.worker.container import create_worker_container


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _setup_worker_container(state: TaskiqState) -> None:
    container = create_worker_container(AppConfig.get())
    state.worker_container = container
    setup_dishka(container, broker)


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _close_worker_container(state: TaskiqState) -> None:
    container: AsyncContainer = state.worker_container
    await container.close()
