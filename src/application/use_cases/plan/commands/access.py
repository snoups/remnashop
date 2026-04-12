from dataclasses import dataclass

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import PlanDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import PlanDto, UserDto
from src.core.exceptions import UserAlreadyAllowedError


@dataclass(frozen=True)
class AddAllowedUserToPlanDto:
    plan: PlanDto
    input_telegram_id: str


class AddAllowedUserToPlan(Interactor[AddAllowedUserToPlanDto, PlanDto]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    async def _execute(self, actor: UserDto, data: AddAllowedUserToPlanDto) -> PlanDto:
        if not data.input_telegram_id.isdigit():
            logger.warning(f"{actor.log} Provided non-numeric user ID: '{data.input_telegram_id}'")
            raise ValueError(f"User ID must be numeric, got '{data.input_telegram_id}'")

        allowed_telegram_id = int(data.input_telegram_id)

        if allowed_telegram_id in data.plan.allowed_user_ids:
            logger.warning(f"{actor.log} User '{allowed_telegram_id}' is already in allowed list")
            raise UserAlreadyAllowedError(f"User '{allowed_telegram_id}' already allowed")

        data.plan.allowed_user_ids.append(allowed_telegram_id)

        logger.info(
            f"{actor.log} Added user '{allowed_telegram_id}' to allowed list of plan in memory"
        )
        return data.plan


@dataclass(frozen=True)
class ToggleUserPlanAccessDto:
    plan_id: int
    telegram_id: int


class ToggleUserPlanAccess(Interactor[ToggleUserPlanAccessDto, None]):
    required_permission = Permission.USER_EDITOR

    def __init__(self, uow: UnitOfWork, plan_dao: PlanDao) -> None:
        self.uow = uow
        self.plan_dao = plan_dao

    async def _execute(self, actor: UserDto, data: ToggleUserPlanAccessDto) -> None:
        async with self.uow:
            plan = await self.plan_dao.get_by_id(data.plan_id)
            if not plan:
                raise ValueError(f"Plan '{data.plan_id}' not found")

            allowed_ids = list(plan.allowed_user_ids)
            if data.telegram_id not in allowed_ids:
                allowed_ids.append(data.telegram_id)
                action = "Granted"
            else:
                allowed_ids.remove(data.telegram_id)
                action = "Revoked"

            plan.allowed_user_ids = allowed_ids
            await self.plan_dao.update(plan)
            await self.uow.commit()

        logger.info(
            f"{actor.log} {action} access to plan '{data.plan_id}' for user '{data.telegram_id}'"
        )
