from typing import Any, Awaitable, Callable, Final, Optional

import orjson
from dishka.integrations.taskiq import FromDishka, inject
from redis.asyncio import Redis

from app.core.broker import broker
from app.core.constants import REDIS_KEY_PREFIX, TTL_1D
from app.core.exceptions import RetryableTaskError
from app.core.utils.lock import cron_lock
from app.modules.notifications.dto import (
    COALESCE_WINDOW_S,
    COALESCED_EVENT_TYPES,
    DeliverNotificationDto,
)
from app.modules.notifications.usecases import DeliverNotificationUseCase

# longer than the outbox sweep keeps retrying a row
_DELIVERED_TTL_S: Final[int] = TTL_1D
# outlives any window until the next flush picks it up
_SUMMARY_TTL_S: Final[int] = TTL_1D
_WINDOW: Final[str] = f"{REDIS_KEY_PREFIX}notification_window:"
_SKIPPED: Final[str] = f"{REDIS_KEY_PREFIX}notification_skipped:"
_LAST: Final[str] = f"{REDIS_KEY_PREFIX}notification_last:"
_SOURCES: Final[str] = f"{REDIS_KEY_PREFIX}notification_sources:"
# a botnet or a rotated IPv6 range is many sources: past this many per window they share one
_MAX_SOURCES_PER_WINDOW: Final[int] = 5
_OVERFLOW_SUFFIX: Final[str] = ":*"
_FLUSH_LOCK_TTL_S: Final[int] = 55


async def deliver_once(redis: Redis, outbox_id: int, run: Callable[[], Awaitable[None]]) -> None:
    # the sweep re-dispatches a row when another subscriber of the event fails
    key = f"{REDIS_KEY_PREFIX}notification_delivered:{outbox_id}"
    if not await redis.set(key, "1", nx=True, ex=_DELIVERED_TTL_S):
        return
    try:
        await run()
    except RetryableTaskError:
        # nothing was sent, so the broker's retry may take the row again
        await redis.delete(key)
        raise


def coalesce_scope(event_type: str, payload: dict[str, Any], ip_address: Optional[str]) -> str:
    # per source: one decoy failure must not hide every other source's alerts
    source = ip_address or payload.get("login") or "-"
    return f"{event_type}:{source}"


async def bounded_scope(redis: Redis, event_type: str, scope: str) -> str:
    if await redis.exists(_WINDOW + scope):
        return scope
    key = _SOURCES + event_type
    opened = await redis.incr(key)
    # NX: only a counter without a TTL gets one, so a worker killed between the two
    # calls can't leave one that never expires and folds every later source together
    await redis.expire(key, COALESCE_WINDOW_S, nx=True)
    return scope if opened <= _MAX_SOURCES_PER_WINDOW else f"{event_type}{_OVERFLOW_SUFFIX}"


async def coalesce(
    redis: Redis, scope: str, payload: dict[str, Any], ip_address: Optional[str]
) -> Optional[int]:
    if not await redis.set(_WINDOW + scope, "1", nx=True, ex=COALESCE_WINDOW_S):
        await redis.incr(_SKIPPED + scope)
        await redis.expire(_SKIPPED + scope, _SUMMARY_TTL_S)
        last = orjson.dumps({"payload": payload, "ip_address": ip_address})
        await redis.set(_LAST + scope, last, ex=_SUMMARY_TTL_S)
        return None
    await redis.delete(_LAST + scope)
    return int(await redis.getdel(_SKIPPED + scope) or 0)


async def release_window(redis: Redis, scope: str, suppressed: int) -> None:
    await redis.delete(_WINDOW + scope)
    if suppressed:
        await redis.incrby(_SKIPPED + scope, suppressed)
        await redis.expire(_SKIPPED + scope, _SUMMARY_TTL_S)


async def flush_coalesced(redis: Redis, use_case: DeliverNotificationUseCase) -> int:
    # a burst that stops is reported once its window closes, not at the next failure
    sent = 0
    async for key in redis.scan_iter(match=_SKIPPED + "*"):
        scope = str(key).removeprefix(_SKIPPED)
        if await redis.exists(_WINDOW + scope):
            continue
        count = int(await redis.getdel(_SKIPPED + scope) or 0)
        raw = await redis.getdel(_LAST + scope)
        if not count or raw is None:
            continue
        last = orjson.loads(raw)
        # the last suppressed failure is shown; the rest are counted under it
        await use_case.system(
            DeliverNotificationDto(
                event_type=scope.split(":", 1)[0],
                payload=last["payload"],
                actor_id=None,
                ip_address=last["ip_address"],
                suppressed=count - 1,
                sources_merged=scope.endswith(_OVERFLOW_SUFFIX),
            )
        )
        sent += 1
    return sent


async def deliver(
    use_case: DeliverNotificationUseCase,
    redis: Redis,
    outbox_id: int,
    event_type: str,
    payload: dict[str, Any],
    actor_id: Optional[int],
    ip_address: Optional[str],
) -> None:
    async def run() -> None:
        suppressed = 0
        scope = coalesce_scope(event_type, payload, ip_address)
        if event_type in COALESCED_EVENT_TYPES:
            scope = await bounded_scope(redis, event_type, scope)
            coalesced = await coalesce(redis, scope, payload, ip_address)
            if coalesced is None:
                return
            suppressed = coalesced
        try:
            await use_case.system(
                DeliverNotificationDto(
                    event_type=event_type,
                    payload=payload,
                    actor_id=actor_id,
                    ip_address=ip_address,
                    suppressed=suppressed,
                    sources_merged=scope.endswith(_OVERFLOW_SUFFIX),
                )
            )
        except RetryableTaskError:
            if event_type in COALESCED_EVENT_TYPES:
                await release_window(redis, scope, suppressed)
            raise

    await deliver_once(redis, outbox_id, run)


@broker.task(retry_on_error=True, max_retries=3)
@inject(patch_module=True)
async def deliver_notification_task(
    use_case: FromDishka[DeliverNotificationUseCase],
    redis: FromDishka[Redis],
    outbox_id: int,
    event_type: str,
    payload: dict[str, Any],
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> None:
    await deliver(use_case, redis, outbox_id, event_type, payload, actor_id, ip_address)


@broker.task(schedule=[{"cron": "*/1 * * * *"}])
@inject(patch_module=True)
async def flush_coalesced_notifications_task(
    use_case: FromDishka[DeliverNotificationUseCase], redis: FromDishka[Redis]
) -> None:
    async with cron_lock(
        redis, "flush_coalesced_notifications", ttl_seconds=_FLUSH_LOCK_TTL_S
    ) as acquired:
        if acquired:
            await flush_coalesced(redis, use_case)
