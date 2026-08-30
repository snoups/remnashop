from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.users import UserDto


class DeletePromocodeUseCase(UseCase[int, None]):
    required_permission = Permission.PROMOCODES_DELETE

    def __init__(self, promocode_repository: PromocodeRepository, uow: UnitOfWork) -> None:
        self._promocode_repository = promocode_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> None:
        async with self._uow:
            await self._promocode_repository.delete(data)
        logger.info(f"{actor.log} Deleted promocode '{data}'")
