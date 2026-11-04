from datetime import timedelta
from typing import Optional

from adaptix.conversion import ConversionRetort
from loguru import logger
from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.common.dao import PromocodeDao
from src.application.dto import (
    PromocodeActivationDto,
    PromocodeDetailStatisticsDto,
    PromocodeDto,
    PromocodeStatisticsDto,
)
from src.core.enums import PromocodeRewardType
from src.core.exceptions import PromocodeAlreadyActivatedError, PromocodeNotAvailableError
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.promocode import Promocode, PromocodeActivation


class PromocodeDaoImpl(PromocodeDao):
    def __init__(self, session: AsyncSession, conversion_retort: ConversionRetort) -> None:
        self.session = session
        self._to_dto = conversion_retort.get_converter(Promocode, PromocodeDto)
        self._to_dto_list = conversion_retort.get_converter(list[Promocode], list[PromocodeDto])
        self._act_to_dto = conversion_retort.get_converter(
            PromocodeActivation, PromocodeActivationDto
        )

    async def create(self, promocode: PromocodeDto) -> PromocodeDto:
        db = Promocode(
            code=promocode.code.upper(),
            is_active=promocode.is_active,
            reward_type=promocode.reward_type,
            reward=promocode.reward,
            plan_snapshot=promocode.plan_snapshot,
            availability=promocode.availability,
            expires_at=promocode.expires_at,
            max_activations=promocode.max_activations,
            is_reusable=promocode.is_reusable,
        )
        self.session.add(db)
        try:
            await self.session.flush()
        except IntegrityError:
            raise ValueError(f"Promocode with code '{promocode.code}' already exists")
        logger.debug(f"Promocode '{promocode.code}' created with id={db.id}")
        return self._to_dto(db)

    async def update(self, promocode: PromocodeDto) -> Optional[PromocodeDto]:
        db = await self.session.get(Promocode, promocode.id)
        if not db:
            logger.warning(f"Promocode id={promocode.id} not found for update")
            return None
        for key, value in promocode.changed_data.items():
            if hasattr(db, key):
                if key == "code":
                    value = value.upper()
                setattr(db, key, value)
        await self.session.flush()
        # Reload eagerly: the server-side ``onupdate`` expires ``updated_at`` after the
        # UPDATE, and the sync DTO converter cannot lazy-load it inside the async session.
        await self.session.refresh(db)
        logger.debug(f"Promocode id={promocode.id} updated")
        return self._to_dto(db)

    async def delete(self, promocode_id: int) -> bool:
        stmt = delete(Promocode).where(Promocode.id == promocode_id).returning(Promocode.id)
        result = await self.session.execute(stmt)
        deleted = result.scalar_one_or_none()
        if deleted:
            logger.debug(f"Promocode id={promocode_id} deleted")
            return True
        logger.debug(f"Promocode id={promocode_id} not found for deletion")
        return False

    async def get_by_id(self, promocode_id: int) -> Optional[PromocodeDto]:
        db = await self.session.get(Promocode, promocode_id)
        return self._to_dto(db) if db else None

    async def get_by_code(self, code: str) -> Optional[PromocodeDto]:
        stmt = select(Promocode).where(Promocode.code == code.upper())
        db = await self.session.scalar(stmt)
        return self._to_dto(db) if db else None

    async def get_list(self, limit: int = 100, offset: int = 0) -> list[PromocodeDto]:
        stmt = select(Promocode).order_by(Promocode.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.scalars(stmt)
        return self._to_dto_list(list(result.all()))

    async def get_activations_count(self, promocode_id: int) -> int:
        result = await self.session.scalar(
            select(func.count(PromocodeActivation.id)).where(
                PromocodeActivation.promocode_id == promocode_id
            )
        )
        return result or 0

    async def get_statistics(self) -> PromocodeStatisticsDto:
        now = datetime_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        promo_counts = (
            (
                await self.session.execute(
                    select(
                        func.count().label("total"),
                        func.sum(case((Promocode.is_active, 1), else_=0)).label("active"),
                    ).select_from(Promocode)
                )
            )
            .mappings()
            .one()
        )

        activated_at = PromocodeActivation.activated_at
        activation_counts = (
            (
                await self.session.execute(
                    select(
                        func.count().label("total"),
                        func.sum(case((activated_at >= today_start, 1), else_=0)).label("today"),
                        func.sum(case((activated_at >= week_ago, 1), else_=0)).label("week"),
                        func.sum(case((activated_at >= month_ago, 1), else_=0)).label("month"),
                    ).select_from(PromocodeActivation)
                )
            )
            .mappings()
            .one()
        )

        by_type_rows = (
            (
                await self.session.execute(
                    select(
                        Promocode.reward_type,
                        func.count(PromocodeActivation.id).label("count"),
                        func.coalesce(func.sum(Promocode.reward), 0).label("reward_sum"),
                    )
                    .join(PromocodeActivation, PromocodeActivation.promocode_id == Promocode.id)
                    .group_by(Promocode.reward_type)
                )
            )
            .mappings()
            .all()
        )

        counts: dict[PromocodeRewardType, int] = {}
        reward_sums: dict[PromocodeRewardType, int] = {}
        for row in by_type_rows:
            counts[row["reward_type"]] = int(row["count"] or 0)
            reward_sums[row["reward_type"]] = int(row["reward_sum"] or 0)

        return PromocodeStatisticsDto(
            total_promocodes=int(promo_counts["total"] or 0),
            active_promocodes=int(promo_counts["active"] or 0),
            total_activations=int(activation_counts["total"] or 0),
            activations_today=int(activation_counts["today"] or 0),
            activations_week=int(activation_counts["week"] or 0),
            activations_month=int(activation_counts["month"] or 0),
            issued_days=reward_sums.get(PromocodeRewardType.DURATION, 0),
            issued_traffic=reward_sums.get(PromocodeRewardType.TRAFFIC, 0),
            issued_devices=reward_sums.get(PromocodeRewardType.DEVICES, 0),
            issued_subscriptions=counts.get(PromocodeRewardType.SUBSCRIPTION, 0),
            issued_personal_discounts=counts.get(PromocodeRewardType.PERSONAL_DISCOUNT, 0),
            issued_purchase_discounts=counts.get(PromocodeRewardType.PURCHASE_DISCOUNT, 0),
        )

    async def get_detail_statistics(
        self, promocode_id: int
    ) -> Optional[PromocodeDetailStatisticsDto]:
        promo = await self.session.get(Promocode, promocode_id)
        if not promo:
            return None

        now = datetime_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        activated_at = PromocodeActivation.activated_at
        counts = (
            (
                await self.session.execute(
                    select(
                        func.count().label("total"),
                        func.sum(case((activated_at >= today_start, 1), else_=0)).label("today"),
                        func.sum(case((activated_at >= week_ago, 1), else_=0)).label("week"),
                        func.sum(case((activated_at >= month_ago, 1), else_=0)).label("month"),
                    ).where(PromocodeActivation.promocode_id == promocode_id)
                )
            )
            .mappings()
            .one()
        )

        return PromocodeDetailStatisticsDto(
            code=promo.code,
            reward_type=promo.reward_type,
            reward=promo.reward,
            plan_snapshot=promo.plan_snapshot,
            is_active=promo.is_active,
            is_reusable=promo.is_reusable,
            created_at=promo.created_at,
            expires_at=promo.expires_at,
            max_activations=promo.max_activations,
            total_activations=int(counts["total"] or 0),
            activations_today=int(counts["today"] or 0),
            activations_week=int(counts["week"] or 0),
            activations_month=int(counts["month"] or 0),
        )

    async def get_activation_by_user(
        self, promocode_id: int, user_id: int
    ) -> Optional[PromocodeActivationDto]:
        stmt = select(PromocodeActivation).where(
            PromocodeActivation.promocode_id == promocode_id,
            PromocodeActivation.user_id == user_id,
        )
        db = await self.session.scalar(stmt)
        return self._act_to_dto(db) if db else None

    async def create_activation(
        self,
        activation: PromocodeActivationDto,
        max_activations: Optional[int] = None,
        is_reusable: bool = False,
    ) -> PromocodeActivationDto:
        # Lock the promocode row so the activation-limit and per-user uniqueness checks
        # below run race-free against concurrent activations of the same promocode.
        if max_activations is not None or not is_reusable:
            await self.session.execute(
                select(Promocode.id)
                .where(Promocode.id == activation.promocode_id)
                .with_for_update()
            )

        if max_activations is not None:
            count_result = await self.session.execute(
                select(func.count(PromocodeActivation.id)).where(
                    PromocodeActivation.promocode_id == activation.promocode_id
                )
            )
            count = count_result.scalar() or 0
            if count >= max_activations:
                raise PromocodeNotAvailableError("Promocode activation limit reached")

        if not is_reusable:
            existing = await self.session.scalar(
                select(PromocodeActivation.id).where(
                    PromocodeActivation.promocode_id == activation.promocode_id,
                    PromocodeActivation.user_id == activation.user_id,
                )
            )
            if existing is not None:
                raise PromocodeAlreadyActivatedError(
                    f"Promocode '{activation.promocode_id}' already activated "
                    f"by user '{activation.user_id}'"
                )

        db = PromocodeActivation(
            promocode_id=activation.promocode_id,
            user_id=activation.user_id,
            activated_at=activation.activated_at,
        )
        self.session.add(db)
        await self.session.flush()
        logger.debug(
            f"PromocodeActivation created: promocode_id={activation.promocode_id}, "
            f"user_id={activation.user_id}"
        )
        return self._act_to_dto(db)
