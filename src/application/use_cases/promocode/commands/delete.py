from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import PromocodeDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import UserDto


class DeletePromocode(Interactor[int, None]):
    required_permission = Permission.VIEW_PROMOCODE

    def __init__(self, uow: UnitOfWork, promocode_dao: PromocodeDao) -> None:
        self.uow = uow
        self.promocode_dao = promocode_dao

    async def _execute(self, actor: UserDto, promocode_id: int) -> None:
        async with self.uow:
            deleted = await self.promocode_dao.delete(promocode_id)
            if not deleted:
                raise ValueError(f"Promocode '{promocode_id}' not found")

            await self.uow.commit()

        logger.info(f"{actor.log} Deleted promocode '{promocode_id}'")
