from typing import Optional

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import PlanAvailability
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import PlanDto, UserDto
from src.infrastructure.database.models.sql import Plan, PlanDuration, PlanPrice
from src.infrastructure.redis import RedisRepository

from .base import BaseService


# TODO: Implement logic for plan availability for specific gateways
# TODO: Make plan sorting customizable for display
# TODO: Implement general discount for plan
class PlanService(BaseService):
    uow: UnitOfWork

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        uow: UnitOfWork,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow

    async def create(self, plan: PlanDto) -> PlanDto:
        order_index = await self.uow.repository.plans.get_max_index()
        order_index = (order_index or 0) + 1
        plan.order_index = order_index

        db_plan = self._dto_to_model(plan)
        db_created_plan = await self.uow.repository.plans.create(db_plan)
        logger.info(f"Created plan '{plan.name}' with ID '{db_created_plan.id}'")
        return PlanDto.from_model(db_created_plan)  # type: ignore[return-value]

    async def get(self, plan_id: int) -> Optional[PlanDto]:
        db_plan = await self.uow.repository.plans.get(plan_id)

        if db_plan:
            logger.debug(f"Retrieved plan '{plan_id}'")
        else:
            logger.warning(f"Plan '{plan_id}' not found")

        return PlanDto.from_model(db_plan)

    async def get_by_name(self, plan_name: str) -> Optional[PlanDto]:
        db_plan = await self.uow.repository.plans.get_by_name(plan_name)

        if db_plan:
            logger.debug(f"Retrieved plan by name '{plan_name}'")
        else:
            logger.warning(f"Plan with name '{plan_name}' not found")

        return PlanDto.from_model(db_plan)

    async def get_all(self) -> list[PlanDto]:
        db_plans = await self.uow.repository.plans.get_all()
        logger.debug(f"Retrieved '{len(db_plans)}' plans")
        return PlanDto.from_model_list(db_plans)

    async def update(self, plan: PlanDto) -> Optional[PlanDto]:
        db_plan = self._dto_to_model(plan)
        db_updated_plan = await self.uow.repository.plans.update(db_plan)

        if db_updated_plan:
            logger.info(f"Updated plan '{plan.name}' (ID: '{plan.id}') successfully")
        else:
            logger.warning(
                f"Attempted to update plan '{plan.name}' (ID: '{plan.id}'), "
                "but plan was not found or update failed"
            )

        return PlanDto.from_model(db_updated_plan)

    async def delete(self, plan_id: int) -> bool:
        result = await self.uow.repository.plans.delete(plan_id)

        if result:
            logger.info(f"Plan '{plan_id}' deleted successfully")
        else:
            logger.warning(f"Failed to delete plan '{plan_id}'. Plan not found or deletion failed")

        return result

    async def count(self) -> int:
        count = await self.uow.repository.plans.count()
        logger.debug(f"Total plans count: '{count}'")
        return count

    #

    async def get_trial_plan(self) -> Optional[PlanDto]:
        db_plans: list[Plan] = await self.uow.repository.plans.filter_by_availability(
            availability=PlanAvailability.TRIAL
        )

        if db_plans:
            if len(db_plans) > 1:
                logger.warning(
                    f"Multiple trial plans found ({len(db_plans)}). "
                    f"Using the first one: '{db_plans[0].name}'"
                )

            db_plan = db_plans[0]

            if db_plan.is_active:
                logger.debug(f"Available trial plan '{db_plans[0].name}'")
                return PlanDto.from_model(db_plans[0])
            else:
                logger.warning(f"Trial plan '{db_plans[0].name}' found but is not active")

        logger.debug(f"No active trial plan found")
        return None

    async def get_available_plans(self, user_dto: UserDto, is_new_user: bool) -> list[PlanDto]:
        logger.debug(f"Fetching available plans for user '{user_dto.telegram_id}'")

        db_plans: list[Plan] = await self.uow.repository.plans.filter_active(is_active=True)
        db_filtered_plans = []

        for db_plan in db_plans:
            match db_plan.availability:
                case PlanAvailability.ALL:
                    db_filtered_plans.append(db_plan)
                case PlanAvailability.NEW if is_new_user:
                    db_filtered_plans.append(db_plan)
                case PlanAvailability.EXISTING if not is_new_user:
                    db_filtered_plans.append(db_plan)
                # case PlanAvailability.INVITED if is_invited_user:
                #     db_filtered_plans.append(db_plan)
                case PlanAvailability.ALLOWED if user_dto.telegram_id in db_plan.allowed_user_ids:
                    db_filtered_plans.append(db_plan)

        logger.info(
            f"Available plans filtered: '{len(db_filtered_plans)}' "
            f"for user '{user_dto.telegram_id}'"
        )
        return PlanDto.from_model_list(db_filtered_plans)

    async def get_allowed_plans(self) -> list[PlanDto]:
        db_plans: list[Plan] = await self.uow.repository.plans.filter_by_availability(
            availability=PlanAvailability.ALLOWED,
        )

        if db_plans:
            logger.debug(
                f"Retrieved '{len(db_plans)}' plans with availability '{PlanAvailability.ALLOWED}'"
            )
        else:
            logger.debug(f"No plans found with availability '{PlanAvailability.ALLOWED}'")

        return PlanDto.from_model_list(db_plans)

    #

    def _dto_to_model(self, plan_dto: PlanDto) -> Plan:
        db_plan = Plan(**plan_dto.model_dump(exclude={"durations"}))

        for duration_dto in plan_dto.durations:
            db_duration = PlanDuration(**duration_dto.model_dump(exclude={"prices"}))
            db_plan.durations.append(db_duration)
            db_duration.plan = db_plan

            for price_dto in duration_dto.prices:
                db_price = PlanPrice(**price_dto.model_dump())
                db_duration.prices.append(db_price)
                db_price.plan_duration = db_duration

        return db_plan
