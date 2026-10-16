from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.passkeys.dto import PasskeyCredentialDto, RenamePasskeyDto
from app.modules.passkeys.events import PasskeyRenamedEvent
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.users import UserDto


class RenamePasskeyUseCase(UseCase[RenamePasskeyDto, PasskeyCredentialDto, UserDto]):
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

    async def _execute(self, actor: UserDto, data: RenamePasskeyDto) -> PasskeyCredentialDto:
        async with self._uow:
            existing = await self._passkey_repository.get_by_id_and_user(data.id, actor.id)
            if existing is None:
                raise NotFoundError("Passkey not found", code=ErrorCode.PASSKEY_NOT_FOUND)

            renamed = await self._passkey_repository.update_name(data.id, data.name)
            await self._event_publisher.publish(
                PasskeyRenamedEvent(user=actor, credential_name=renamed.name)
            )
            return renamed
