from typing import Final

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from prometheus_client import Gauge
from redis.asyncio import Redis

from app.core.metrics import WORKER_METRICS_REGISTRY
from app.core.utils.lock import cron_lock
from app.core.utils.time import datetime_now
from app.modules.event_log.outbox_repository import OutboxLagStats
from app.modules.event_log.usecases import (
    ProcessOutboxEntryUseCase,
    PruneOutboxUseCase,
    SweepOutboxUseCase,
)
from app.worker.broker import broker

_SWEEP_LOCK_TTL_S: Final[int] = 55

OUTBOX_UNPROCESSED: Final[Gauge] = Gauge(
    "remnashop_event_outbox_unprocessed",
    "Unprocessed event outbox rows",
    registry=WORKER_METRICS_REGISTRY,
)
OUTBOX_OLDEST_AGE: Final[Gauge] = Gauge(
    "remnashop_event_outbox_oldest_unprocessed_age_seconds",
    "Age of the oldest unprocessed event outbox row",
    registry=WORKER_METRICS_REGISTRY,
)


def _record_outbox_lag_metrics(stats: OutboxLagStats) -> None:
    OUTBOX_UNPROCESSED.set(stats.unprocessed_count)
    if stats.oldest_occurred_at is None:
        OUTBOX_OLDEST_AGE.set(0)
    else:
        OUTBOX_OLDEST_AGE.set(max((datetime_now() - stats.oldest_occurred_at).total_seconds(), 0))


@broker.task
@inject(patch_module=True)
async def process_outbox_entry_task(
    outbox_id: int, use_case: FromDishka[ProcessOutboxEntryUseCase]
) -> None:
    await use_case.system(outbox_id)


@broker.task(schedule=[{"cron": "*/1 * * * *"}])
@inject(patch_module=True)
async def sweep_outbox_task(
    use_case: FromDishka[SweepOutboxUseCase], redis: FromDishka[Redis]
) -> None:
    async with cron_lock(redis, "sweep_outbox", ttl_seconds=_SWEEP_LOCK_TTL_S) as acquired:
        if not acquired:
            logger.debug("sweep_outbox_task already running, skipping this tick")
            return
        _record_outbox_lag_metrics(await use_case.system())


@broker.task(schedule=[{"cron": "0 3 * * *"}])
@inject(patch_module=True)
async def prune_outbox_task(use_case: FromDishka[PruneOutboxUseCase]) -> None:
    await use_case.system()
