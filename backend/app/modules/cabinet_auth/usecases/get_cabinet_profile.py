from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users import UserDto


class GetCabinetProfileUseCase(UseCase[None, UserDto, UserDto]):
    required_permission = Permission.PUBLIC

    async def _execute(self, actor: UserDto, data: None) -> UserDto:
        return actor
