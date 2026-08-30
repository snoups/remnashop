from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import AddOnDto, CreateAddOnDto
from app.modules.users import UserDto


class CreateAddOnUseCase(UseCase[CreateAddOnDto, AddOnDto]):
    required_permission = Permission.ADDONS_CREATE

    def __init__(self, addon_repository: AddOnRepository, uow: UnitOfWork) -> None:
        self._addon_repository = addon_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: CreateAddOnDto) -> AddOnDto:
        async with self._uow:
            addon = await self._addon_repository.create(data)
        logger.info(f"{actor.log} Created addon '{addon.name}'")
        return addon
