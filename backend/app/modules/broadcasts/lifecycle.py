from typing import Final

from app.core.enums import BroadcastStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dto import BroadcastDto
from app.modules.broadcasts.repository import BroadcastRepository

EDITABLE: Final[frozenset[BroadcastStatus]] = frozenset(
    {BroadcastStatus.DRAFT, BroadcastStatus.SCHEDULED}
)


async def lock_editable(repository: BroadcastRepository, broadcast_id: int) -> BroadcastDto:
    current = await repository.get_by_id_for_update(broadcast_id)
    if current.status not in EDITABLE or current.started_at is not None:
        raise ConflictError(
            f"Broadcast '{current.id}' is {current.status}",
            code=ErrorCode.BROADCAST_INVALID_STATUS,
        )
    return current


async def cancel_sending(repository: BroadcastRepository, broadcast_id: int) -> None:
    await repository.update_fields(
        broadcast_id, status=BroadcastStatus.CANCELED, completed_at=datetime_now()
    )
    await repository.cancel_pending(broadcast_id)
    await repository.refresh_counts(broadcast_id)
