from typing import Any, Awaitable, Callable, Final, Optional

from dishka.integrations.taskiq import FromDishka, inject
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX
from app.core.exceptions import RetryableTaskError
from app.modules.notifications.dto import DeliverNotificationDto
from app.modules.notifications.usecases import DeliverNotificationUseCase
from app.worker.broker import broker

# longer than the outbox sweep keeps retrying a row
_DELIVERED_TTL_S: Final[int] = 24 * 60 * 60


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
    data = DeliverNotificationDto(
        event_type=event_type, payload=payload, actor_id=actor_id, ip_address=ip_address
    )
    await deliver_once(redis, outbox_id, lambda: use_case.system(data))
