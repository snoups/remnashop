import asyncio
import contextlib

from redis.asyncio import Redis
from taskiq import TaskiqEvents, TaskiqScheduler, TaskiqState
from taskiq.schedule_sources import LabelScheduleSource

from app.core.config import AppConfig
from app.core.logger import setup_logger
from app.core.runtime_heartbeat import poll_runtime_heartbeat
from app.worker.broker import broker, retry_schedule_source

scheduler = TaskiqScheduler(
    broker=broker, sources=[LabelScheduleSource(broker), retry_schedule_source]
)


@broker.on_event(TaskiqEvents.CLIENT_STARTUP)
async def _setup_logging(state: TaskiqState) -> None:
    # its own file: two processes rotating one file clobber each other
    setup_logger(AppConfig.get(), "scheduler")


# `taskiq scheduler` never imports app.worker.lifespan, and its broker.startup()
# fires CLIENT_STARTUP, not WORKER_STARTUP. No dishka container here either,
# hence a standalone Redis client.
@broker.on_event(TaskiqEvents.CLIENT_STARTUP)
async def _start_runtime_heartbeat(state: TaskiqState) -> None:
    redis = Redis.from_url(AppConfig.get().redis.dsn, decode_responses=True)
    state.scheduler_redis = redis
    state.runtime_heartbeat_task = asyncio.create_task(poll_runtime_heartbeat(redis, "scheduler"))


@broker.on_event(TaskiqEvents.CLIENT_SHUTDOWN)
async def _stop_runtime_heartbeat(state: TaskiqState) -> None:
    runtime_heartbeat_task = getattr(state, "runtime_heartbeat_task", None)
    if runtime_heartbeat_task is not None:
        runtime_heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await runtime_heartbeat_task
    redis = getattr(state, "scheduler_redis", None)
    if redis is not None:
        await redis.aclose()
