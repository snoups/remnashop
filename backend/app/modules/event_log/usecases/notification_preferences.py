from app.core.db.uow import UnitOfWork
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.event_log.dto import DEFAULT_NOTIFICATION_GROUPS, NOTIFICATION_GROUPS
from app.modules.users import UserDto, UserRepository


# Own settings only, hence the own-account permission.
class GetNotificationGroupsUseCase(UseCase[None, list[str]]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    async def _execute(self, actor: UserDto, data: None) -> list[str]:
        if actor.notification_groups is None:
            return sorted(DEFAULT_NOTIFICATION_GROUPS)
        return [g for g in actor.notification_groups if g in NOTIFICATION_GROUPS]


class UpdateNotificationGroupsUseCase(UseCase[list[str], list[str]]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, user_repository: UserRepository, uow: UnitOfWork) -> None:
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: list[str]) -> list[str]:
        unknown = set(data) - NOTIFICATION_GROUPS.keys()
        if unknown:
            raise ValidationError(f"Unknown notification groups: {', '.join(sorted(unknown))}")
        groups = sorted(set(data))
        async with self._uow:
            await self._user_repository.set_notification_groups(actor.id, groups)
        return groups
