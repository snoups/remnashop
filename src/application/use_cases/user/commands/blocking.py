from dataclasses import dataclass

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import UserDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import UserDto


@dataclass(frozen=True)
class SetBotBlockedStatusDto:
    telegram_id: int
    is_blocked: bool


class SetBotBlockedStatus(Interactor[SetBotBlockedStatusDto, None]):
    required_permission = None

    def __init__(self, uow: UnitOfWork, user_dao: UserDao) -> None:
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: SetBotBlockedStatusDto) -> None:
        async with self.uow:
            await self.user_dao.set_bot_blocked_status(data.telegram_id, data.is_blocked)
            await self.uow.commit()

        logger.info(f"Set bot blocked status for user '{data.telegram_id}' to '{data.is_blocked}'")


class ToggleUserBlockedStatus(Interactor[int, None]):
    required_permission = Permission.USER_EDITOR

    def __init__(self, uow: UnitOfWork, user_dao: UserDao) -> None:
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, telegram_id: int) -> None:
        async with self.uow:
            await self.user_dao.toggle_blocked_status(telegram_id)
            await self.uow.commit()

        logger.info(f"{actor.log} Toggled user '{telegram_id}' blocked status")


class UnblockAllUsers(Interactor[None, int]):
    required_permission = Permission.UNBLOCK_ALL

    def __init__(self, uow: UnitOfWork, user_dao: UserDao) -> None:
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: None) -> int:
        blocked_count = await self.user_dao.count_blocked()

        if blocked_count > 0:
            async with self.uow:
                await self.user_dao.unblock_all()
                await self.uow.commit()

            logger.warning(f"{actor.log} Unblocked all '{blocked_count}' users")
        else:
            logger.info(f"{actor.log} Attempted to unblock all, but blacklist is empty")

        return blocked_count
