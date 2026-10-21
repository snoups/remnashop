from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.notifications.dto import (
    NOTIFICATION_GROUPS,
    NotificationChannel,
    NotificationChannelsDto,
    UpdateNotificationChannelsDto,
)
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.usecases._channels import to_channels_dto
from app.modules.users import UserDto, UserRepository


class UpdateNotificationChannelsUseCase(
    UseCase[UpdateNotificationChannelsDto, NotificationChannelsDto, UserDto]
):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(
        self,
        user_repository: UserRepository,
        notification_repository: NotificationRepository,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._notification_repository = notification_repository
        self._uow = uow

    async def _execute(
        self, actor: UserDto, data: UpdateNotificationChannelsDto
    ) -> NotificationChannelsDto:
        known_channels = {c.value for c in NotificationChannel}
        requested = data.channels
        unknown = (set(requested) - NOTIFICATION_GROUPS.keys()) | {
            c for channels in requested.values() for c in channels if c not in known_channels
        }
        if unknown:
            raise ValidationError(
                f"Unknown notification groups or channels: {', '.join(sorted(unknown))}",
                code=ErrorCode.NOTIFICATION_CHANNELS_INVALID,
            )
        matrix = {
            group.value: sorted(set(requested.get(group, []))) for group in NOTIFICATION_GROUPS
        }
        async with self._uow:
            await self._user_repository.set_notification_channels(actor.id, matrix)
            updated = actor.model_copy(update={"notification_channels": matrix})
            return await to_channels_dto(updated, self._notification_repository)
