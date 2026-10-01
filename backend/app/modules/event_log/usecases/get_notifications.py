from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.event_log.dto import (
    NOTIFICATIONS_LIMIT,
    NotificationsDto,
    notification_event_types,
)
from app.modules.event_log.repository import EventLogRepository
from app.modules.users import UserDto


class GetNotificationsUseCase(UseCase[None, NotificationsDto, UserDto]):
    required_permission = Permission.NOTIFICATIONS_VIEW

    def __init__(self, event_log_repository: EventLogRepository, uow: UnitOfWork) -> None:
        self._event_log_repository = event_log_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> NotificationsDto:
        event_types = notification_event_types(actor.notification_groups)
        async with self._uow:
            items = await self._event_log_repository.list_notifications(
                event_types=event_types,
                exclude_actor_id=actor.id,
                limit=NOTIFICATIONS_LIMIT,
            )
            unread_count = await self._event_log_repository.count_notifications_since(
                event_types=event_types,
                exclude_actor_id=actor.id,
                since=actor.notifications_seen_at,
            )
        return NotificationsDto(items=items, unread_count=unread_count)
