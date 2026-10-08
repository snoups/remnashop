from typing import Final

from dishka.integrations.taskiq import FromDishka, inject
from redis.asyncio import Redis

from app.core.utils.lock import cron_lock
from app.modules.broadcasts.usecases import (
    DeliverBroadcastBatchUseCase,
    PruneBroadcastRecipientsUseCase,
    RecallBroadcastBatchUseCase,
    StartBroadcastUseCase,
    TickBroadcastsUseCase,
)
from app.worker.broker import broker

_TICK_LOCK_TTL_S: Final[int] = 55
_PRUNE_LOCK_TTL_S: Final[int] = 60 * 60


@broker.task
@inject(patch_module=True)
async def start_broadcast_task(
    broadcast_id: int, use_case: FromDishka[StartBroadcastUseCase]
) -> None:
    await use_case.system(broadcast_id)


@broker.task
@inject(patch_module=True)
async def deliver_broadcast_task(
    broadcast_id: int, use_case: FromDishka[DeliverBroadcastBatchUseCase]
) -> None:
    await use_case.system(broadcast_id)


@broker.task
@inject(patch_module=True)
async def recall_broadcast_task(
    broadcast_id: int, use_case: FromDishka[RecallBroadcastBatchUseCase]
) -> None:
    await use_case.system(broadcast_id)


@broker.task(schedule=[{"cron": "*/1 * * * *"}])
@inject(patch_module=True)
async def tick_broadcasts_task(
    use_case: FromDishka[TickBroadcastsUseCase], redis: FromDishka[Redis]
) -> None:
    async with cron_lock(redis, "tick_broadcasts", ttl_seconds=_TICK_LOCK_TTL_S) as acquired:
        if acquired:
            await use_case.system()


@broker.task(schedule=[{"cron": "30 3 * * *"}])
@inject(patch_module=True)
async def prune_broadcast_recipients_task(
    use_case: FromDishka[PruneBroadcastRecipientsUseCase], redis: FromDishka[Redis]
) -> None:
    async with cron_lock(
        redis, "prune_broadcast_recipients", ttl_seconds=_PRUNE_LOCK_TTL_S
    ) as acquired:
        if acquired:
            await use_case.system()
