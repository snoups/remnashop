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
from app.modules.broadcasts.dto import BroadcastDto
from app.modules.broadcasts.events import BroadcastCanceledEvent
from app.modules.broadcasts.repository import BroadcastRepository


async def cancel_sending(repository: BroadcastRepository, broadcast_id: int) -> None:
    await repository.update_fields(
        broadcast_id, status=BroadcastStatus.CANCELED, completed_at=datetime_now()
    )
    await repository.cancel_pending(broadcast_id)
    await repository.refresh_counts(broadcast_id)


class CancelBroadcastUseCase(UseCase[int, BroadcastDto]):
    required_permission = Permission.BROADCASTS_CANCEL

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: int) -> BroadcastDto:
        async with self._uow:
            broadcast = await self._broadcast_repository.lock_for_update(data)
            if broadcast.status is BroadcastStatus.SCHEDULED:
                await self._broadcast_repository.update_fields(
                    data,
                    status=BroadcastStatus.CANCELED,
                    scheduled_at=None,
                    completed_at=datetime_now(),
                )
                await self._broadcast_repository.cancel_pending(data)
                await self._broadcast_repository.refresh_counts(data)
            elif broadcast.status is BroadcastStatus.SENDING:
                await cancel_sending(self._broadcast_repository, data)
            else:
                raise ConflictError(
                    f"Broadcast '{data}' is {broadcast.status}",
                    code=ErrorCode.BROADCAST_INVALID_STATUS,
                )
            await self._event_publisher.publish(
                BroadcastCanceledEvent(user=actor, broadcast_id=data)
            )
            result = await self._broadcast_repository.get_or_raise(data)
        logger.info(f"{actor.log} Canceled broadcast '{data}'")
        return result
