from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import AddOnDto, SetAddOnPriceOverrideDto
from app.modules.users import UserDto


class SetAddOnPriceOverrideUseCase(UseCase[SetAddOnPriceOverrideDto, AddOnDto]):
    required_permission = Permission.ADDONS_PRICE_OVERRIDE_MANAGE

    def __init__(self, addon_repository: AddOnRepository, uow: UnitOfWork) -> None:
        self._addon_repository = addon_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: SetAddOnPriceOverrideDto) -> AddOnDto:
        async with self._uow:
            addon = await self._addon_repository.set_price_override(data)
        logger.info(
            f"{actor.log} Set price override for addon '{data.addon_id}' currency '{data.currency}'"
        )
        return addon
