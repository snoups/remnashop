from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistRepository
from app.modules.users.dto import UserDto
from app.modules.users.events import UserUnblockedEvent
from app.modules.users.repository import UserRepository


class UnblockUserUseCase(UseCase[int, UserDto]):
    required_permission = Permission.USERS_UNBLOCK

    def __init__(
        self,
        user_repository: UserRepository,
        blacklist_repository: BlacklistRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._user_repository = user_repository
        self._blacklist_repository = blacklist_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, user_id: int) -> UserDto:
        async with self._uow:
            target = await self._user_repository.get_by_id(user_id)
            if target is None:
                raise NotFoundError(f"User {user_id} not found", code=ErrorCode.USER_NOT_FOUND)
            if not PermissionPolicy.can_manage(actor, target):
                raise PermissionDeniedError

        async with self._uow:
            updated = await self._user_repository.set_blocked(user_id, False)
            if updated is None:
                raise NotFoundError(f"User {user_id} not found", code=ErrorCode.USER_NOT_FOUND)
            if target.telegram_id is not None:
                await self._blacklist_repository.remove_entry(
                    BlacklistKind.TELEGRAM_ID, str(target.telegram_id)
                )
            if target.email is not None:
                await self._blacklist_repository.remove_entry(BlacklistKind.EMAIL, target.email)
            await self._event_publisher.publish(UserUnblockedEvent(actor=actor, target=updated))

        return updated
