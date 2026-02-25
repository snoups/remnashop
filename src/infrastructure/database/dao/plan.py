from typing import Optional, cast

from adaptix import Retort
from adaptix.conversion import ConversionRetort
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.application.common.dao import PlanDao
from src.application.dto import PlanDto
from src.core.enums import PlanAvailability
from src.infrastructure.database.models import Plan, PlanDuration, PlanPrice


class PlanDaoImpl(PlanDao):
    def __init__(
        self,
        session: AsyncSession,
        retort: Retort,
        conversion_retort: ConversionRetort,
        redis: Redis,
    ) -> None:
        self.session = session
        self.retort = retort
        self.conversion_retort = conversion_retort
        self.redis = redis

        self._convert_to_dto = self.conversion_retort.get_converter(Plan, PlanDto)
        self._convert_to_dto_list = self.conversion_retort.get_converter(list[Plan], list[PlanDto])

    async def create(self, plan: PlanDto) -> PlanDto:
        plan_data = self.retort.dump(plan)
        durations_data = plan_data.pop("durations", [])

        db_plan = Plan(**plan_data)

        for duration_data in durations_data:
            prices_data = duration_data.pop("prices", [])
            db_duration = PlanDuration(**duration_data)

            for price_data in prices_data:
                db_duration.prices.append(PlanPrice(**price_data))

            db_plan.durations.append(db_duration)

        self.session.add(db_plan)
        await self.session.flush()

        logger.debug(f"New plan '{plan.name}' created with '{len(plan.durations)}' durations")
        return self._convert_to_dto(db_plan)

    async def get_by_id(self, plan_id: int) -> Optional[PlanDto]:
        stmt = (
            select(Plan)
            .where(Plan.id == plan_id)
            .options(selectinload(Plan.durations).selectinload(PlanDuration.prices))
        )
        db_plan = await self.session.scalar(stmt)

        if db_plan:
            logger.debug(f"Plan '{plan_id}' found")
            return self._convert_to_dto(db_plan)

        logger.debug(f"Plan '{plan_id}' not found")
        return None

    async def get_by_name(self, name: str) -> Optional[PlanDto]:
        stmt = (
            select(Plan)
            .where(Plan.name == name)
            .options(selectinload(Plan.durations).selectinload(PlanDuration.prices))
        )
        db_plan = await self.session.scalar(stmt)

        if db_plan:
            logger.debug(f"Plan with name '{name}' found")
            return self._convert_to_dto(db_plan)

        logger.debug(f"Plan with name '{name}' not found")
        return None

    async def get_active_plans(self) -> list[PlanDto]:
        stmt = (
            select(Plan)
            .where(Plan.is_active.is_(True), Plan.is_trial.is_(False))
            .options(selectinload(Plan.durations).selectinload(PlanDuration.prices))
            .order_by(Plan.order_index.asc())
        )
        result = await self.session.execute(stmt)
        db_plans = result.scalars().all()

        logger.info(f"Retrieved '{len(db_plans)}' active plans")
        return self._convert_to_dto_list(list(db_plans))

    async def get_active_trial_plans(self) -> list[PlanDto]:
        stmt = (
            select(Plan)
            .where(Plan.is_active.is_(True), Plan.is_trial.is_(True))
            .options(selectinload(Plan.durations).selectinload(PlanDuration.prices))
            .order_by(Plan.order_index.asc())
        )
        result = await self.session.execute(stmt)
        db_plans = result.scalars().all()

        logger.info(f"Retrieved '{len(db_plans)}' active trial plans")
        return self._convert_to_dto_list(list(db_plans))

    async def get_all(self) -> list[PlanDto]:
        stmt = (
            select(Plan)
            .options(selectinload(Plan.durations).selectinload(PlanDuration.prices))
            .order_by(Plan.order_index.asc())
        )
        result = await self.session.scalars(stmt)
        db_plans = cast(list, result.all())

        logger.debug(f"Retrieved '{len(db_plans)}' all plans")
        return self._convert_to_dto_list(db_plans)

    async def update(self, plan: PlanDto) -> Optional[PlanDto]:
        stmt = (
            select(Plan)
            .where(Plan.id == plan.id)
            .options(selectinload(Plan.durations).selectinload(PlanDuration.prices))
        )

        db_plan = await self.session.scalar(stmt)

        if not db_plan:
            raise ValueError(f"Plan with id {plan.id} not found")

        exclude_fields = {"id", "durations", "created_at", "updated_at"}
        for key, value in plan.__dict__.items():
            if key not in exclude_fields and hasattr(db_plan, key):
                setattr(db_plan, key, value)

        new_durations = []
        for d_dto in plan.durations:
            new_prices = [
                PlanPrice(currency=p_dto.currency, price=p_dto.price) for p_dto in d_dto.prices
            ]

            new_durations.append(
                PlanDuration(days=d_dto.days, order_index=d_dto.order_index, prices=new_prices)
            )

        db_plan.durations = new_durations

        await self.session.flush()

        refresh_stmt = (
            select(Plan)
            .where(Plan.id == db_plan.id)
            .options(selectinload(Plan.durations).selectinload(PlanDuration.prices))
            .execution_options(populate_existing=True)
        )
        refreshed_plan = await self.session.scalar(refresh_stmt)

        if refreshed_plan:
            logger.info(f"Plan '{refreshed_plan.id}' fully updated with all nested entities")
            return self._convert_to_dto(refreshed_plan)

        return None

    async def update_status(self, plan_id: int, is_active: bool) -> Optional[PlanDto]:
        stmt = update(Plan).where(Plan.id == plan_id).values(is_active=is_active).returning(Plan)
        db_plan = await self.session.scalar(stmt)

        if db_plan:
            logger.debug(f"Active status for plan '{plan_id}' set to '{is_active}'")
            return self._convert_to_dto(db_plan)

        logger.warning(f"Failed to update status for plan '{plan_id}': plan not found")
        return None

    async def delete(self, plan_id: int) -> bool:
        stmt = delete(Plan).where(Plan.id == plan_id).returning(Plan.id)
        result = await self.session.execute(stmt)
        deleted_id = result.scalar_one_or_none()

        if deleted_id:
            logger.debug(f"Plan '{plan_id}' and related data deleted")
            return True

        logger.debug(f"Plan '{plan_id}' not found for deletion")
        return False

    async def filter_by_availability(self, availability: PlanAvailability) -> list[PlanDto]:
        stmt = (
            select(Plan)
            .where(Plan.availability == availability)
            .options(selectinload(Plan.durations).selectinload(PlanDuration.prices))
            .order_by(Plan.order_index.asc())
        )

        result = await self.session.execute(stmt)
        db_plans = result.scalars().all()

        logger.info(f"Retrieved '{len(db_plans)}' plans with availability '{availability}'")
        return self._convert_to_dto_list(list(db_plans))

    async def get_active_allowed_plans(self) -> list[PlanDto]:
        stmt = (
            select(Plan)
            .where(Plan.availability == PlanAvailability.ALLOWED, Plan.is_active.is_(True))
            .options(selectinload(Plan.durations).selectinload(PlanDuration.prices))
            .order_by(Plan.order_index.asc())
        )

        result = await self.session.execute(stmt)
        db_plans = result.scalars().all()

        logger.info(
            f"Retrieved '{len(db_plans)}' active plans with "
            f"availability '{PlanAvailability.ALLOWED}'"
        )
        return self._convert_to_dto_list(list(db_plans))

    async def count_non_trial(self) -> int:
        stmt = select(func.count(Plan.id)).where(Plan.is_active.is_(True), Plan.is_trial.is_(False))
        count = await self.session.scalar(stmt) or 0
        logger.debug(f"Counted '{count}' non-trial active plans")
        return count
