from dataclasses import dataclass

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import UserDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import UserDto


@dataclass(frozen=True)
class SetUserPersonalDiscountDto:
    telegram_id: int
    discount: int


class SetUserPersonalDiscount(Interactor[SetUserPersonalDiscountDto, None]):
    required_permission = Permission.USER_EDITOR

    def __init__(self, uow: UnitOfWork, user_dao: UserDao) -> None:
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: SetUserPersonalDiscountDto) -> None:
        if not (0 <= data.discount <= 100):
            raise ValueError(f"Invalid discount value '{data.discount}'")

        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(data.telegram_id)
            if not target_user:
                raise ValueError(f"User '{data.telegram_id}' not found")

            target_user.personal_discount = data.discount
            await self.user_dao.update(target_user)
            await self.uow.commit()

        logger.info(
            f"{actor.log} Set personal discount to '{data.discount}' for user '{data.telegram_id}'"
        )


@dataclass(frozen=True)
class SetUserPurchaseDiscountDto:
    telegram_id: int
    discount: int


class SetUserPurchaseDiscount(Interactor[SetUserPurchaseDiscountDto, None]):
    required_permission = Permission.USER_EDITOR

    def __init__(self, uow: UnitOfWork, user_dao: UserDao) -> None:
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: SetUserPurchaseDiscountDto) -> None:
        if not (0 <= data.discount <= 100):
            raise ValueError(f"Invalid discount value '{data.discount}'")

        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(data.telegram_id)
            if not target_user:
                raise ValueError(f"User '{data.telegram_id}' not found")

            target_user.purchase_discount = data.discount
            await self.user_dao.update(target_user)
            await self.uow.commit()

        logger.info(
            f"{actor.log} Set purchase discount to '{data.discount}' for user '{data.telegram_id}'"
        )


class ToggleUserTrialAvailable(Interactor[int, None]):
    required_permission = Permission.USER_EDITOR

    def __init__(self, uow: UnitOfWork, user_dao: UserDao) -> None:
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: int) -> None:
        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(data)
            if not target_user:
                raise ValueError(f"User '{data}' not found")

            new_value = not target_user.is_trial_available
            await self.user_dao.set_trial_available(data, new_value)
            await self.uow.commit()

        logger.info(f"{actor.log} Set trial available to '{new_value}' for user '{data}'")


@dataclass(frozen=True)
class ChangeUserPointsDto:
    telegram_id: int
    amount: int


class ChangeUserPoints(Interactor[ChangeUserPointsDto, None]):
    required_permission = Permission.USER_EDITOR

    def __init__(self, uow: UnitOfWork, user_dao: UserDao) -> None:
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: ChangeUserPointsDto) -> None:
        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(data.telegram_id)
            if not target_user:
                logger.error(f"{actor.log} User not found with id '{data.telegram_id}'")
                raise ValueError(f"User '{data.telegram_id}' not found")

            new_points = target_user.points + data.amount
            if new_points < 0:
                raise ValueError(
                    f"{actor.log} Points balance cannot be negative for '{data.telegram_id}'"
                )

            target_user.points = new_points
            await self.user_dao.update(target_user)
            await self.uow.commit()

        operation = "Added" if data.amount > 0 else "Subtracted"
        logger.info(f"{actor.log} {operation} '{abs(data.amount)}' points for '{data.telegram_id}'")
