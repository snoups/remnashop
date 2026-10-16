from typing import Final

from loguru import logger

from app.core.enums import BroadcastStatus
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.broadcasts.events import BroadcastCompletedEvent, BroadcastFailedEvent
from app.modules.broadcasts.repository import BroadcastRepository

_STOPPED: Final[str] = "stopped"


async def complete_broadcast(
    repository: BroadcastRepository, publisher: EventPublisher, broadcast_id: int
) -> None:
    # the caller holds the broadcast row lock and has seen it SENDING: one chain completes it
    counts = await repository.refresh_counts(broadcast_id)
    await repository.update_fields(
        broadcast_id, status=BroadcastStatus.COMPLETED, completed_at=datetime_now()
    )
    await publisher.publish(
        BroadcastCompletedEvent(
            broadcast_id=broadcast_id,
            sent=counts.sent_count,
            failed=counts.failed_count,
            blocked=counts.blocked_count,
        )
    )
    logger.info(f"Broadcast '{broadcast_id}' completed")


async def fail_broadcast(
    repository: BroadcastRepository, publisher: EventPublisher, broadcast_id: int, error: str
) -> None:
    try:
        broadcast = await repository.get_by_id_for_update(broadcast_id)
    except NotFoundError:
        return
    if broadcast.status is not BroadcastStatus.SENDING:
        return
    await repository.update_fields(
        broadcast_id, status=BroadcastStatus.FAILED, completed_at=datetime_now()
    )
    # FAILED, not CANCELED: a retry after fixing the cause resends them
    await repository.fail_pending(broadcast_id, _STOPPED)
    await repository.refresh_counts(broadcast_id)
    await publisher.publish(BroadcastFailedEvent(broadcast_id=broadcast_id, error=error))
    logger.warning(f"Broadcast '{broadcast_id}' failed: {error}")
