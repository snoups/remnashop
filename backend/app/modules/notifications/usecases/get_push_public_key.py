from typing import Optional

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.notifications.repository import NotificationRepository
from app.modules.users import UserDto


class GetPushPublicKeyUseCase(UseCase[None, Optional[str], UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, notification_repository: NotificationRepository, uow: UnitOfWork) -> None:
        self._notification_repository = notification_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> Optional[str]:
        async with self._uow:
            return (await self._notification_repository.get_settings()).vapid_public_key
