import asyncio
import contextlib
from typing import Optional

from dishka import AsyncContainer
from dishka.integrations.taskiq import setup_dishka
from prometheus_client import GCCollector, PlatformCollector, ProcessCollector, start_http_server
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine
from taskiq import TaskiqEvents, TaskiqState

from app.core.config import AppConfig
from app.core.event_bus import EventBus
from app.core.metrics import register_db_pool_metrics
from app.core.runtime_heartbeat import poll_runtime_heartbeat
from app.worker.broker import RETRY_SCHEDULE_PREFIX, broker
from app.worker.container import create_worker_container
from app.worker.metrics import WORKER_METRICS_REGISTRY, poll_worker_gauges
from app.worker.subscribers import register_all_subscribers


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _setup_worker_container(state: TaskiqState) -> None:
    config = AppConfig.get()
    ProcessCollector(registry=WORKER_METRICS_REGISTRY)
    PlatformCollector(registry=WORKER_METRICS_REGISTRY)
    GCCollector(registry=WORKER_METRICS_REGISTRY)
    start_http_server(config.metrics_port, registry=WORKER_METRICS_REGISTRY)
    container = create_worker_container(config)
    state.worker_container = container
    setup_dishka(container, broker)
    register_all_subscribers(await container.get(EventBus))
    engine = await container.get(AsyncEngine)
    register_db_pool_metrics(engine, registry=WORKER_METRICS_REGISTRY)
    redis = await container.get(Redis)
    state.worker_gauges_task = asyncio.create_task(
        poll_worker_gauges(redis, broker.queue_name, RETRY_SCHEDULE_PREFIX)
    )
    state.runtime_heartbeat_task = asyncio.create_task(poll_runtime_heartbeat(redis, "worker"))


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _close_worker_container(state: TaskiqState) -> None:
    worker_gauges_task = getattr(state, "worker_gauges_task", None)
    if worker_gauges_task is not None:
        worker_gauges_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_gauges_task
    runtime_heartbeat_task = getattr(state, "runtime_heartbeat_task", None)
    if runtime_heartbeat_task is not None:
        runtime_heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await runtime_heartbeat_task
    container: Optional[AsyncContainer] = getattr(state, "worker_container", None)
    if container is None:
        return
    event_bus = await container.get(EventBus)
    await event_bus.shutdown()
    await container.close()
