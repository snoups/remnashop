from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import UserDto


class GetCurrentUserUseCase(UseCase[None, UserDto, UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    async def _execute(self, actor: UserDto, data: None) -> UserDto:
        return actor
