from typing import Final

from app.core.enums import BroadcastStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.modules.broadcasts.dto import BroadcastDto
from app.modules.broadcasts.repository import BroadcastRepository

EDITABLE: Final[frozenset[BroadcastStatus]] = frozenset(
    {BroadcastStatus.DRAFT, BroadcastStatus.SCHEDULED}
)


async def lock_editable(repository: BroadcastRepository, broadcast_id: int) -> BroadcastDto:
    current = await repository.lock_for_update(broadcast_id)
    if current.status not in EDITABLE or current.started_at is not None:
        raise ConflictError(
            f"Broadcast '{current.id}' is {current.status}",
            code=ErrorCode.BROADCAST_INVALID_STATUS,
        )
    return current
