from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.passkeys.dto import PasskeyCredentialDto
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.users import UserDto


class ListPasskeysUseCase(UseCase[None, list[PasskeyCredentialDto]]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, passkey_repository: PasskeyRepository) -> None:
        self._passkey_repository = passkey_repository

    async def _execute(self, actor: UserDto, data: None) -> list[PasskeyCredentialDto]:
        return await self._passkey_repository.list_by_user(actor.id)
