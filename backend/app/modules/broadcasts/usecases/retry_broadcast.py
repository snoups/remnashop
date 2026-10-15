from functools import partial
from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import BroadcastStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dispatch import StartBroadcastDispatch
from app.modules.broadcasts.dto import BroadcastDto
from app.modules.broadcasts.events import BroadcastChangedEvent
from app.modules.broadcasts.repository import BroadcastRepository

# FAILED: a stopped send left its unsent rows FAILED too
_RETRYABLE: Final[frozenset[BroadcastStatus]] = frozenset(
    {BroadcastStatus.COMPLETED, BroadcastStatus.CANCELED, BroadcastStatus.FAILED}
)


class RetryBroadcastUseCase(UseCase[int, BroadcastDto]):
    required_permission = Permission.BROADCASTS_RETRY

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        start_dispatch: StartBroadcastDispatch,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._start_dispatch = start_dispatch
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: int) -> BroadcastDto:
        async with self._uow:
            broadcast = await self._broadcast_repository.get_by_id_for_update(data)
            # recalled messages are gone for good; resending would contradict the recall
            if (
                broadcast.status not in _RETRYABLE
                or broadcast.recall_requested_at is not None
                or (await self._broadcast_repository.refresh_counts(data)).recalled_count > 0
                or await self._broadcast_repository.reset_failed(data) == 0
            ):
                raise ConflictError(
                    f"Broadcast '{data}' has nothing to retry",
                    code=ErrorCode.BROADCAST_INVALID_STATUS,
                )
            await self._broadcast_repository.update_fields(
                data,
                status=BroadcastStatus.SCHEDULED,
                scheduled_at=datetime_now(),
                completed_at=None,
            )
            result = await self._broadcast_repository.refresh_counts(data)
            await self._event_publisher.publish(
                BroadcastChangedEvent(actor=actor, action="retry", broadcast_id=data)
            )
            await self._uow.after_commit(partial(self._start_dispatch.kiq, broadcast_id=data))
        logger.info(f"{actor.log} Retrying broadcast '{data}'")
        return result
