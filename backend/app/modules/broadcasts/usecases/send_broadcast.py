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
from app.modules.broadcasts.dispatch import StartBroadcastDispatch
from app.modules.broadcasts.dto import BroadcastDto, SendBroadcastDto
from app.modules.broadcasts.events import BroadcastScheduledEvent
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.settings import SettingsRepository

SCHEDULE_TOLERANCE: Final[timedelta] = timedelta(minutes=1)


class SendBroadcastUseCase(UseCase[SendBroadcastDto, BroadcastDto]):
    required_permission = Permission.BROADCASTS_SEND

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        settings_repository: SettingsRepository,
        start_dispatch: StartBroadcastDispatch,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._settings_repository = settings_repository
        self._start_dispatch = start_dispatch
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: SendBroadcastDto) -> BroadcastDto:
        now = datetime_now()
        scheduled_at = data.scheduled_at or now
        if scheduled_at < now - SCHEDULE_TOLERANCE:
            raise ValidationError(
                "Send time is in the past", code=ErrorCode.BROADCAST_SCHEDULE_IN_PAST
            )
        async with self._uow:
            broadcast = await self._broadcast_repository.lock_for_update(data.broadcast_id)
            if broadcast.status is not BroadcastStatus.DRAFT:
                raise ConflictError(
                    f"Broadcast '{broadcast.id}' is {broadcast.status}",
                    code=ErrorCode.BROADCAST_INVALID_STATUS,
                )
            bot = await self._settings_repository.get_bot_settings()
            if bot.token is None:
                raise ValidationError(
                    "Bot token is not set", code=ErrorCode.BROADCAST_BOT_NOT_CONFIGURED
                )
            if broadcast.post_to_channel:
                requirements = await self._settings_repository.get_bot_requirements()
                if requirements.channel_id is None:
                    raise ValidationError(
                        "Channel is not set", code=ErrorCode.BROADCAST_CHANNEL_NOT_CONFIGURED
                    )
            await self._broadcast_repository.update_fields(
                broadcast.id, status=BroadcastStatus.SCHEDULED, scheduled_at=scheduled_at
            )
            await self._event_publisher.publish(
                BroadcastScheduledEvent(
                    user=actor, broadcast_id=broadcast.id, scheduled_at=scheduled_at.isoformat()
                )
            )
            if scheduled_at <= now:
                await self._uow.after_commit(
                    lambda: self._start_dispatch.kiq(broadcast_id=broadcast.id)
                )
            result = await self._broadcast_repository.get_or_raise(broadcast.id)
        logger.info(
            f"{actor.log} Scheduled broadcast '{broadcast.id}' at {scheduled_at.isoformat()}"
        )
        return result
