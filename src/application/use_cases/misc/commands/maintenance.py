from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import BroadcastDao, TransactionDao
from src.application.common.uow import UnitOfWork
from src.application.dto import UserDto


class CancelOldTransactions(Interactor[None, None]):
    required_permission = None

    def __init__(self, uow: UnitOfWork, transaction_dao: TransactionDao) -> None:
        self.uow = uow
        self.transaction_dao = transaction_dao

    async def _execute(self, actor: UserDto, data: None) -> None:
        async with self.uow:
            await self.transaction_dao.cancel_old()
            await self.uow.commit()

        logger.info("Canceled old transactions from database")


class ClearOldBroadcasts(Interactor[None, None]):
    required_permission = None

    def __init__(self, uow: UnitOfWork, broadcast_dao: BroadcastDao) -> None:
        self.uow = uow
        self.broadcast_dao = broadcast_dao

    async def _execute(self, actor: UserDto, data: None) -> None:
        async with self.uow:
            await self.broadcast_dao.delete_old()
            await self.uow.commit()

        logger.info("Cleaned up old broadcasts from database")
