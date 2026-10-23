from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import DeleteUserDto
from app.modules.users.events import UserDeletedEvent
from app.modules.users.ports import PasskeyRevoker, SessionRevoker, SubscriptionRevoker
from app.modules.users.repository import UserRepository


class DeleteUserUseCase(UseCase[DeleteUserDto, None]):
    required_permission = Permission.USERS_DELETE

    def __init__(
        self,
        user_repository: UserRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        subscription_revoker: SubscriptionRevoker,
        session_revoker: SessionRevoker,
        passkey_revoker: PasskeyRevoker,
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._subscription_revoker = subscription_revoker
        self._session_revoker = session_revoker
        self._passkey_revoker = passkey_revoker

    async def _execute(self, actor: Actor, data: DeleteUserDto) -> None:
        async with self._uow:
            target = await self._user_repository.find_live_for_update(data.user_id)
            if target is None:
                raise NotFoundError("User not found", code=ErrorCode.USER_NOT_FOUND)
            if not target.is_customer:
                raise ConflictError(
                    "Target is not a deletable user", code=ErrorCode.USER_NOT_DELETABLE
                )
            if target.id == actor.id:
                raise ConflictError(
                    "Cannot delete your own account", code=ErrorCode.CANNOT_DELETE_SELF
                )

            # Panel access goes first and inside the transaction: if the panel
            # call fails, nothing local changes and VPN access isn't orphaned.
            await self._subscription_revoker.revoke_all_by_user(target.id)
            await self._session_revoker.revoke_all_by_user(target.id)
            await self._passkey_revoker.delete_all_by_user(target.id)
            deleted = await self._user_repository.anonymize(target.id)
            if deleted is None:
                raise NotFoundError("User not found", code=ErrorCode.USER_NOT_FOUND)
            await self._event_publisher.publish(
                UserDeletedEvent(actor=actor, target=target, ip_address=data.client_ip)
            )
