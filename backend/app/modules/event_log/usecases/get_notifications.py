from typing import Final

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.event_log.dto import NOTIFICATIONS_LIMIT, EventLogEntryDto, NotificationsDto
from app.modules.event_log.repository import EventLogRepository
from app.modules.notifications import bell_event_types
from app.modules.users import UserDto

_KEPT_USER_FIELDS: Final[tuple[str, ...]] = ("id", "login", "name", "role")
_USER_KEYS: Final[tuple[str, ...]] = ("user", "target", "actor")


def _trimmed(entry: EventLogEntryDto) -> EventLogEntryDto:
    payload = {
        key: (
            {k: v for k, v in value.items() if k in _KEPT_USER_FIELDS}
            if key in _USER_KEYS and isinstance(value, dict)
            else value
        )
        for key, value in entry.payload.items()
    }
    return entry.model_copy(update={"payload": payload, "actor_email": None})


class GetNotificationsUseCase(UseCase[None, NotificationsDto, UserDto]):
    required_permission = Permission.NOTIFICATIONS_VIEW

    def __init__(self, event_log_repository: EventLogRepository, uow: UnitOfWork) -> None:
        self._event_log_repository = event_log_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> NotificationsDto:
        event_types = bell_event_types(actor)
        async with self._uow:
            items = await self._event_log_repository.list_notifications(
                event_types=event_types,
                exclude_actor_id=actor.id,
                limit=NOTIFICATIONS_LIMIT,
                after=actor.notifications_cleared_at,
            )
            unread_count = await self._event_log_repository.count_notifications_since(
                event_types=event_types,
                exclude_actor_id=actor.id,
                since=actor.notifications_seen_at,
            )
        if not PermissionPolicy.has_permission(actor, Permission.EVENT_LOG_DETAIL_VIEW):
            items = [_trimmed(item) for item in items]
        return NotificationsDto(items=items, unread_count=unread_count)
