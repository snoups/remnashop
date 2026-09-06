from app.core.db.uow import UnitOfWork
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.users import UserDto


class DeletePasskeyUseCase(UseCase[int, None]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, passkey_repository: PasskeyRepository, uow: UnitOfWork) -> None:
        self._passkey_repository = passkey_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> None:
        async with self._uow:
            deleted = await self._passkey_repository.delete_by_id_and_user(data, actor.id)
        if not deleted:
            raise NotFoundError("Passkey not found")
