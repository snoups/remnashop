import asyncio
from typing import Final

from loguru import logger
from prometheus_client import Gauge
from redis.asyncio import Redis

from app.core.metrics import WORKER_METRICS_REGISTRY

QUEUE_DEPTH: Final[Gauge] = Gauge(
    "remnashop_taskiq_queue_depth",
    "Pending messages in the taskiq Redis list queue",
    registry=WORKER_METRICS_REGISTRY,
)

SCHEDULED_RETRIES: Final[Gauge] = Gauge(
    "remnashop_taskiq_scheduled_retries",
    "Pending scheduled taskiq retries",
    registry=WORKER_METRICS_REGISTRY,
)

_WORKER_GAUGE_POLL_INTERVAL_S: Final[float] = 15.0


async def _sample_queue_depth(redis: Redis, queue_name: str) -> None:
    QUEUE_DEPTH.set(await redis.llen(queue_name))  # type: ignore[misc]


async def _sample_scheduled_retries(redis: Redis, schedule_prefix: str) -> None:
    count = 0
    async for _ in redis.scan_iter(f"{schedule_prefix}:data:*", count=1000):
        count += 1
    SCHEDULED_RETRIES.set(count)


async def poll_worker_gauges(redis: Redis, queue_name: str, retry_schedule_prefix: str) -> None:
    while True:
        try:
            await _sample_queue_depth(redis, queue_name)
            await _sample_scheduled_retries(redis, retry_schedule_prefix)
        except Exception:  # a transient Redis blip must not kill the poller
            logger.warning("Failed to sample taskiq worker gauges")
        await asyncio.sleep(_WORKER_GAUGE_POLL_INTERVAL_S)
