from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import AddOnDto
from app.modules.users import UserDto


class ListAddOnsUseCase(UseCase[None, list[AddOnDto]]):
    required_permission = Permission.ADDONS_VIEW

    def __init__(self, addon_repository: AddOnRepository) -> None:
        self._addon_repository = addon_repository

    async def _execute(self, actor: UserDto, data: None) -> list[AddOnDto]:
        return await self._addon_repository.list_all()
