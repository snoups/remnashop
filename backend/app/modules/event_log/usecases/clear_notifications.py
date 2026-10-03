from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.users import UserDto, UserRepository


# Own bell only, hence the own-account permission rather than a new one.
class ClearNotificationsUseCase(UseCase[None, None, UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, user_repository: UserRepository, uow: UnitOfWork) -> None:
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> None:
        async with self._uow:
            await self._user_repository.clear_notifications(actor.id, datetime_now())
