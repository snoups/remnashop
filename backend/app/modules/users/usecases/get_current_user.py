from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import UserDto


class GetCurrentUserUseCase(UseCase[None, UserDto, UserDto]):
    # reading one's own profile is every user's right
    required_permission = Permission.PUBLIC

    async def _execute(self, actor: UserDto, data: None) -> UserDto:
        return actor
