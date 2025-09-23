from typing import Optional

from aiogram import Bot
from fluentogram import TranslatorHub
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
        db_plan = self._dto_to_model(plan)
        db_created_plan = await self.uow.repository.plans.create(db_plan)
        return PlanDto.from_model(db_created_plan)  # type: ignore[return-value]

    async def get(self, plan_id: int) -> Optional[PlanDto]:
        db_plan = await self.uow.repository.plans.get(plan_id)
        return PlanDto.from_model(db_plan)

    async def get_by_name(self, plan_name: str) -> Optional[PlanDto]:
        db_plan = await self.uow.repository.plans.get_by_name(plan_name)
        return PlanDto.from_model(db_plan)

    async def get_all(self) -> list[PlanDto]:
        db_plans = await self.uow.repository.plans.get_all()
        return PlanDto.from_model_list(db_plans)

    async def update(self, plan: PlanDto) -> Optional[PlanDto]:
        db_plan = self._dto_to_model(plan)
        db_updated_plan = await self.uow.repository.plans.update(db_plan)
        return PlanDto.from_model(db_updated_plan)

    async def delete(self, plan_id: int) -> bool:
        return await self.uow.repository.plans.delete(plan_id)

    #

    async def get_available_plans(self, user_dto: UserDto) -> list[PlanDto]:
        db_plans: list[Plan] = await self.uow.repository.plans.filter_active(is_active=True)

        # is_new_user = user_dto.subscription_status is None
        # is_existing_user = user_dto.subscription_status is not None
        # is_invited_user = user_dto.is_invited

        db_filtered_plans = []
        for db_plan in db_plans:
            match db_plan.availability:
                case PlanAvailability.ALL:
                    db_filtered_plans.append(db_plan)
                # case PlanAvailability.NEW if is_new_user:
                #     db_filtered_plans.append(db_plan)
                # case PlanAvailability.EXISTING if is_existing_user:
                #     db_filtered_plans.append(db_plan)
                # case PlanAvailability.INVITED if is_invited_user:
                #     db_filtered_plans.append(db_plan)
                case PlanAvailability.ALLOWED if user_dto.telegram_id in db_plan.allowed_user_ids:
                    db_filtered_plans.append(db_plan)

        return PlanDto.from_model_list(db_filtered_plans)

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
