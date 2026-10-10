from datetime import timedelta
from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import BroadcastStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dispatch import RecallBroadcastDispatch
from app.modules.broadcasts.dto import BroadcastDto
from app.modules.broadcasts.events import BroadcastRecalledEvent
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.usecases.cancel_broadcast import cancel_sending

RECALL_WINDOW: Final[timedelta] = timedelta(hours=48)
# since the chain's last batch: a repeat while it works would delete the same rows twice
RECALL_REPEAT_AFTER: Final[timedelta] = timedelta(minutes=5)
_RECALLABLE: Final[frozenset[BroadcastStatus]] = frozenset(
    {BroadcastStatus.SENDING, BroadcastStatus.COMPLETED, BroadcastStatus.CANCELED}
)


class RecallBroadcastUseCase(UseCase[int, BroadcastDto]):
    required_permission = Permission.BROADCASTS_RECALL

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        recall_dispatch: RecallBroadcastDispatch,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._recall_dispatch = recall_dispatch
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: int) -> BroadcastDto:
        now = datetime_now()
        async with self._uow:
            broadcast = await self._broadcast_repository.lock_for_update(data)
            if broadcast.status not in _RECALLABLE or broadcast.started_at is None:
                raise ConflictError(
                    f"Broadcast '{data}' is {broadcast.status}",
                    code=ErrorCode.BROADCAST_INVALID_STATUS,
                )
            # a repeat picks up deletes Telegram didn't confirm the first time
            if broadcast.recall_requested_at is not None:
                if now - broadcast.recall_requested_at < RECALL_REPEAT_AFTER:
                    raise ConflictError(
                        f"Broadcast '{data}' recall is still running",
                        code=ErrorCode.BROADCAST_RECALL_IN_PROGRESS,
                    )
                left = await self._broadcast_repository.count_recallable(data)
                if left == 0 and broadcast.channel_message_id is None:
                    raise ConflictError(
                        f"Broadcast '{data}' has nothing left to recall",
                        code=ErrorCode.BROADCAST_INVALID_STATUS,
                    )
            if now - broadcast.started_at > RECALL_WINDOW:
                raise ValidationError(
                    "Recall window has passed", code=ErrorCode.BROADCAST_RECALL_EXPIRED
                )
            await self._broadcast_repository.clear_recall_failures(data)
            await self._broadcast_repository.update_fields(data, recall_requested_at=now)
            if broadcast.status is BroadcastStatus.SENDING:
                await cancel_sending(self._broadcast_repository, data)
            await self._event_publisher.publish(
                BroadcastRecalledEvent(user=actor, broadcast_id=data)
            )
            await self._uow.after_commit(lambda: self._recall_dispatch.kiq(broadcast_id=data))
            result = await self._broadcast_repository.get_or_raise(data)
            result = result.model_copy(
                update={"recallable_count": await self._broadcast_repository.count_recallable(data)}
            )
        logger.info(f"{actor.log} Recalling broadcast '{data}'")
        return result
