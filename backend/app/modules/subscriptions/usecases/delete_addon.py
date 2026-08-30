from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.users import UserDto


class DeleteAddOnUseCase(UseCase[int, None]):
    required_permission = Permission.ADDONS_DELETE

    def __init__(self, addon_repository: AddOnRepository, uow: UnitOfWork) -> None:
        self._addon_repository = addon_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> None:
        async with self._uow:
            await self._addon_repository.delete(data)
        logger.info(f"{actor.log} Deleted addon '{data}'")
