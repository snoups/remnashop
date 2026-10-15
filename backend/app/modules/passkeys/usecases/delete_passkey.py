from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.passkeys.dto import DeletePasskeyDto
from app.modules.passkeys.events import PasskeyRemovedEvent
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.users import UserDto


class DeletePasskeyUseCase(UseCase[DeletePasskeyDto, None, UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(
        self,
        passkey_repository: PasskeyRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._passkey_repository = passkey_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: DeletePasskeyDto) -> None:
        async with self._uow:
            credential = await self._passkey_repository.get_by_id_and_user(
                data.passkey_id, actor.id
            )
            if credential is None:
                raise NotFoundError("Passkey not found", code=ErrorCode.PASSKEY_NOT_FOUND)

            deleted = await self._passkey_repository.delete_by_id_and_user(
                data.passkey_id, actor.id
            )
            if not deleted:
                raise NotFoundError("Passkey not found", code=ErrorCode.PASSKEY_NOT_FOUND)
            await self._event_publisher.publish(
                PasskeyRemovedEvent(
                    user=actor, credential_name=credential.name, ip_address=data.client_ip
                )
            )
