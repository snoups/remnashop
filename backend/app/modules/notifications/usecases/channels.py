from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.notifications.dto import (
    NOTIFICATION_GROUPS,
    NotificationChannel,
    NotificationChannelsDto,
    effective_matrix,
)
from app.modules.notifications.repository import NotificationRepository
from app.modules.users import UserDto, UserRepository


async def _to_dto(user: UserDto, repository: NotificationRepository) -> NotificationChannelsDto:
    return NotificationChannelsDto(
        channels=effective_matrix(user),
        push_configured=await repository.is_push_configured(),
        telegram_available=user.telegram_id is not None,
    )


class GetNotificationChannelsUseCase(UseCase[None, NotificationChannelsDto, UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, notification_repository: NotificationRepository, uow: UnitOfWork) -> None:
        self._notification_repository = notification_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> NotificationChannelsDto:
        async with self._uow:
            return await _to_dto(actor, self._notification_repository)


class UpdateNotificationChannelsUseCase(
    UseCase[dict[str, list[str]], NotificationChannelsDto, UserDto]
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

    async def _execute(self, actor: UserDto, data: dict[str, list[str]]) -> NotificationChannelsDto:
        known_channels = {c.value for c in NotificationChannel}
        unknown = (set(data) - NOTIFICATION_GROUPS.keys()) | {
            c for channels in data.values() for c in channels if c not in known_channels
        }
        if unknown:
            raise ValidationError(
                f"Unknown notification groups or channels: {', '.join(sorted(unknown))}",
                code=ErrorCode.NOTIFICATION_CHANNELS_INVALID,
            )
        # every group is stored, so a group left out of the request is switched off
        matrix = {group: sorted(set(data.get(group, []))) for group in NOTIFICATION_GROUPS}
        async with self._uow:
            await self._user_repository.set_notification_channels(actor.id, matrix)
            updated = actor.model_copy(update={"notification_channels": matrix})
            return await _to_dto(updated, self._notification_repository)
