from typing import Optional

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import PlanDao, UserDao
from src.application.common.policy import Permission
from src.application.dto import PlanDto, UserDto
from src.core.enums import PlanAvailability


class GetAvailablePlans(Interactor[UserDto, list[PlanDto]]):
    required_permission = None

    def __init__(self, user_dao: UserDao, plan_dao: PlanDao):
        self.user_dao = user_dao
        self.plan_dao = plan_dao

    async def _execute(self, actor: UserDto, data: UserDto) -> list[PlanDto]:
        all_active_plans = await self.plan_dao.get_active_plans()

        filtered_plans: list[PlanDto] = []

        has_any_subscription = await self.user_dao.has_any_subscription(
            data.telegram_id,
            include_trial=False,
        )
        is_invited_user = await self.user_dao.is_invited_user(data.telegram_id)

        for plan in all_active_plans:
            match plan.availability:
                case PlanAvailability.ALL:
                    filtered_plans.append(plan)

                case PlanAvailability.NEW if not has_any_subscription:
                    logger.info(f"{data.log} Eligible for new user plan '{plan.name}'")
                    filtered_plans.append(plan)

                case PlanAvailability.EXISTING if has_any_subscription:
                    logger.info(f"{data.log} Eligible for existing user plan '{plan.name}'")
                    filtered_plans.append(plan)

                case PlanAvailability.INVITED if is_invited_user:
                    logger.info(f"{data.log} Eligible for invited user plan '{plan.name}'")
                    filtered_plans.append(plan)

                case PlanAvailability.ALLOWED if data.telegram_id in plan.allowed_user_ids:
                    logger.info(f"{data.log} Explicitly allowed for plan '{plan.name}'")
                    filtered_plans.append(plan)

        logger.info(
            f"{data.log} Filtered '{len(filtered_plans)}' available plans "
            f"out of '{len(all_active_plans)}' active"
        )
        return filtered_plans


class GetAvailableTrial(Interactor[UserDto, Optional[PlanDto]]):
    required_permission = None

    def __init__(self, user_dao: UserDao, plan_dao: PlanDao):
        self.user_dao = user_dao
        self.plan_dao = plan_dao

    async def _execute(self, actor: UserDto, data: UserDto) -> Optional[PlanDto]:  # noqa: C901
        active_trials = await self.plan_dao.get_active_trial_plans()

        if not active_trials:
            logger.info(f"{data.log} No active trial plans found")
            return None

        has_subscription = await self.user_dao.has_any_subscription(
            data.telegram_id,
            include_trial=False,
        )
        is_invited = await self.user_dao.is_invited_user(data.telegram_id)

        priority_map = {
            PlanAvailability.ALLOWED: 4,
            PlanAvailability.INVITED: 3,
            PlanAvailability.NEW: 2,
            PlanAvailability.ALL: 1,
        }

        eligible_plans: list[tuple[int, PlanDto]] = []

        for plan in active_trials:
            is_eligible = False

            match plan.availability:
                case PlanAvailability.ALLOWED:
                    if data.telegram_id in (plan.allowed_user_ids or []):
                        is_eligible = True
                case PlanAvailability.INVITED:
                    if is_invited:
                        is_eligible = True
                case PlanAvailability.NEW:
                    if not has_subscription:
                        is_eligible = True
                case PlanAvailability.ALL:
                    is_eligible = True

            if is_eligible:
                priority = priority_map.get(plan.availability, 0)
                eligible_plans.append((priority, plan))

        if not eligible_plans:
            logger.info(f"{data.log} No eligible trial plans found for user")
            return None

        eligible_plans.sort(key=lambda x: (-x[0], x[1].order_index))

        available_plan = eligible_plans[0][1]

        logger.info(
            f"{data.log} Selected available trial plan '{available_plan.id}' "
            f"with availability '{available_plan.availability}'"
        )
        return available_plan


class GetAvailablePlanByCode(Interactor[str, Optional[PlanDto]]):
    required_permission = Permission.PUBLIC

    def __init__(self, plan_dao: PlanDao, user_dao: UserDao):
        self.plan_dao = plan_dao
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, code: str) -> Optional[PlanDto]:
        plan = await self.plan_dao.get_by_public_code(code)

        if not plan or not plan.is_active:
            logger.info(f"{actor.log} Plan with code '{code}' not found or inactive")
            return None

        is_available = await self._check_availability(actor, plan)

        if not is_available:
            logger.info(f"{actor.log} Plan with code '{code}' is not available for user")
            return None

        return plan

    async def _check_availability(self, user: UserDto, plan: PlanDto) -> bool:
        if plan.is_trial and not user.is_trial_available:
            return False

        has_subscription = await self.user_dao.has_any_subscription(
            user.telegram_id,
            include_trial=False,
        )
        is_invited_user = await self.user_dao.is_invited_user(user.telegram_id)

        match plan.availability:
            case PlanAvailability.LINK:
                return True
            case PlanAvailability.ALL:
                return True
            case PlanAvailability.NEW:
                return not has_subscription
            case PlanAvailability.EXISTING:
                return has_subscription
            case PlanAvailability.INVITED:
                return is_invited_user
            case PlanAvailability.ALLOWED:
                return user.telegram_id in plan.allowed_user_ids
            case _:
                return False
