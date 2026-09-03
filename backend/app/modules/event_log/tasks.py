from datetime import datetime, timedelta
from typing import Any, Final, Optional

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from prometheus_client import Gauge
from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.event_bus import EventBus
from app.core.events import EventCategory, StoredEvent
from app.core.utils.lock import cron_lock
from app.core.utils.time import datetime_now
from app.modules.event_log.dto import EventLogEntryDto
from app.modules.event_log.outbox_repository import EventOutboxRepository, OutboxLagStats
from app.modules.event_log.repository import EventLogRepository
from app.worker.broker import broker
from app.worker.metrics import WORKER_METRICS_REGISTRY

_OUTBOX_RETENTION_DAYS: Final[int] = 14
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


async def persist_event_entry(
    repository: EventLogRepository,
    *,
    category: EventCategory,
    event_type: str,
    occurred_at: datetime,
    payload: dict[str, Any],
    outbox_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    actor_login: Optional[str] = None,
    actor_name: Optional[str] = None,
    actor_email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    await repository.create(
        EventLogEntryDto(
            category=category,
            event_type=event_type,
            occurred_at=occurred_at,
            actor_id=actor_id,
            actor_login=actor_login,
            actor_name=actor_name,
            actor_email=actor_email,
            ip_address=ip_address,
            payload=payload,
            outbox_id=outbox_id,
        )
    )


async def _process_outbox_entry(
    uow: UnitOfWork,
    outbox_repository: EventOutboxRepository,
    event_log_repository: EventLogRepository,
    bus: EventBus,
    entry_id: int,
) -> None:
    try:
        async with uow:
            row = await outbox_repository.get_unprocessed_by_id(entry_id)
            if row is None:
                return  # already processed, gone, or locked by another processor
            stored = StoredEvent(
                outbox_id=row.id,
                category=row.category,
                event_type=row.event_type,
                occurred_at=row.occurred_at,
                payload=row.payload,
                actor_id=row.actor_id,
                actor_login=row.actor_login,
                actor_name=row.actor_name,
                actor_email=row.actor_email,
                ip_address=row.ip_address,
            )
            await persist_event_entry(
                event_log_repository,
                outbox_id=row.id,
                category=row.category,
                event_type=row.event_type,
                occurred_at=row.occurred_at,
                payload=row.payload,
                actor_id=row.actor_id,
                actor_login=row.actor_login,
                actor_name=row.actor_name,
                actor_email=row.actor_email,
                ip_address=row.ip_address,
            )
            error_message = await bus.dispatch_stored(stored)
            if error_message is not None:
                # Handler failed. The audit row above still commits (idempotent
                # on retry via outbox_id). Leave the row unprocessed so the next
                # sweep re-dispatches; the attempts cap eventually stops it.
                await outbox_repository.record_failure(row.id, error=error_message)
            else:
                await outbox_repository.mark_processed(row.id)
    except Exception as error:  # noqa: BLE001
        # dispatch_stored never raises -- only a genuine DB error in persist /
        # record_failure / mark_processed reaches here, poisoning that
        # transaction. Record the failure in a fresh one so attempts still
        # advances toward the cap.
        async with uow:
            await outbox_repository.record_failure(entry_id, error=str(error))


@broker.task
@inject(patch_module=True)
async def process_outbox_entry_task(
    outbox_id: int,
    outbox_repository: FromDishka[EventOutboxRepository],
    event_log_repository: FromDishka[EventLogRepository],
    bus: FromDishka[EventBus],
    uow: FromDishka[UnitOfWork],
) -> None:
    await _process_outbox_entry(uow, outbox_repository, event_log_repository, bus, outbox_id)


@broker.task(schedule=[{"cron": "*/1 * * * *"}])
@inject(patch_module=True)
async def sweep_outbox_task(
    outbox_repository: FromDishka[EventOutboxRepository],
    event_log_repository: FromDishka[EventLogRepository],
    bus: FromDishka[EventBus],
    uow: FromDishka[UnitOfWork],
    redis: FromDishka[Redis],
) -> None:
    async with cron_lock(redis, "sweep_outbox", ttl_seconds=_SWEEP_LOCK_TTL_S) as acquired:
        if not acquired:
            logger.debug("sweep_outbox_task already running, skipping this tick")
            return
        async with uow:
            entry_ids = await outbox_repository.list_unprocessed_ids(limit=100)
            _record_outbox_lag_metrics(await outbox_repository.get_lag_stats())
        for entry_id in entry_ids:
            await _process_outbox_entry(uow, outbox_repository, event_log_repository, bus, entry_id)


@broker.task(schedule=[{"cron": "0 3 * * *"}])
@inject(patch_module=True)
async def prune_outbox_task(
    outbox_repository: FromDishka[EventOutboxRepository],
    uow: FromDishka[UnitOfWork],
) -> None:
    async with uow:
        cutoff = datetime_now() - timedelta(days=_OUTBOX_RETENTION_DAYS)
        deleted = await outbox_repository.delete_processed_before(cutoff)
        poisoned = await outbox_repository.count_poisoned()
    logger.info(
        f"Pruned {deleted} processed outbox row(s) older than {_OUTBOX_RETENTION_DAYS}d; "
        f"{poisoned} poisoned row(s) remain unprocessed"
    )
