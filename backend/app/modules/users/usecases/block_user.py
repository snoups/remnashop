from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistRepository
from app.modules.users.dto import UserDto
from app.modules.users.events import UserBlockedEvent
from app.modules.users.repository import UserRepository


class BlockUserUseCase(UseCase[int, UserDto]):
    required_permission = Permission.USERS_BLOCK

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

    async def _execute(self, actor: UserDto, user_id: int) -> UserDto:
        target = await self._user_repository.get_by_id(user_id)
        if target is None:
            raise NotFoundError(f"User {user_id} not found")
        # Not a role comparison: an API token authenticates as a synthetic
        # actor with Role.USER, so `actor.role > target.role` refused it every
        # target, including the plain users its own scopes cover. What has to
        # hold is that staff are only ever acted on from above.
        if target.is_privileged and not actor.role > target.role:
            raise PermissionDeniedError

        async with self._uow:
            updated = await self._user_repository.set_blocked(user_id, True)
            if updated is None:
                raise NotFoundError(f"User {user_id} not found")
            if target.telegram_id is not None:
                await self._blacklist_repository.add_entry(
                    BlacklistKind.TELEGRAM_ID, str(target.telegram_id)
                )
            if target.email is not None:
                await self._blacklist_repository.add_entry(BlacklistKind.EMAIL, target.email)
            await self._event_publisher.publish(UserBlockedEvent(actor=actor, target=updated))

        return updated
