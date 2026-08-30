from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import AddOnDto, ReorderAddOnsDto
from app.modules.users import UserDto


class ReorderAddOnsUseCase(UseCase[ReorderAddOnsDto, list[AddOnDto]]):
    required_permission = Permission.ADDONS_REORDER

    def __init__(self, addon_repository: AddOnRepository, uow: UnitOfWork) -> None:
        self._addon_repository = addon_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: ReorderAddOnsDto) -> list[AddOnDto]:
        async with self._uow:
            addons = await self._addon_repository.reorder(data)
        logger.info(f"{actor.log} Reordered addons")
        return addons
