import asyncio
import contextlib

from redis.asyncio import Redis
from taskiq import TaskiqEvents, TaskiqScheduler, TaskiqState
from taskiq.schedule_sources import LabelScheduleSource

from app.core.config import AppConfig
from app.core.runtime_heartbeat import poll_runtime_heartbeat
from app.worker.broker import broker, retry_schedule_source

scheduler = TaskiqScheduler(
    broker=broker, sources=[LabelScheduleSource(broker), retry_schedule_source]
)


# `taskiq scheduler` never imports app.worker.lifespan, and its broker.startup()
# fires CLIENT_STARTUP (is_scheduler_process, not is_worker_process) -- so the
# worker's WORKER_STARTUP hook never runs here. This process has no dishka
# container either, hence a standalone Redis client (same idiom as
# app/telegram/restart_listener.py).
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
