from typing import Optional, cast

from adaptix import Retort
from adaptix.conversion import ConversionRetort
from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.common.dao import PromocodeDao
from src.application.dto import PromocodeActivationDto, PromocodeDto
from src.infrastructure.database.models import Promocode, PromocodeActivation


class PromocodeDaoImpl(PromocodeDao):
    def __init__(
        self,
        session: AsyncSession,
        retort: Retort,
        conversion_retort: ConversionRetort,
    ) -> None:
        self.session = session
        self.retort = retort
        self.conversion_retort = conversion_retort

        self._to_dto = self.conversion_retort.get_converter(Promocode, PromocodeDto)
        self._to_dto_list = self.conversion_retort.get_converter(list[Promocode], list[PromocodeDto])
        self._to_activation_dto = self.conversion_retort.get_converter(
            PromocodeActivation, PromocodeActivationDto
        )

    async def create(self, promocode: PromocodeDto) -> PromocodeDto:
        db_obj = Promocode(
            code=promocode.code,
            discount_percent=promocode.discount_percent,
            plan_id=promocode.plan_id,
            audience=promocode.audience,
            max_activations=promocode.max_activations,
            expires_at=promocode.expires_at,
            is_active=promocode.is_active,
        )
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj, attribute_names=["plan"])

        logger.debug(f"Created promocode '{db_obj.code}' (id={db_obj.id})")
        return self._to_dto(db_obj)

    async def get_by_id(self, promocode_id: int) -> Optional[PromocodeDto]:
        stmt = select(Promocode).where(Promocode.id == promocode_id)
        db_obj = await self.session.scalar(stmt)

        if db_obj:
            logger.debug(f"Promocode id='{promocode_id}' found")
            return self._to_dto(db_obj)

        logger.debug(f"Promocode id='{promocode_id}' not found")
        return None

    async def get_by_code(self, code: str) -> Optional[PromocodeDto]:
        stmt = select(Promocode).where(Promocode.code == code)
        db_obj = await self.session.scalar(stmt)

        if db_obj:
            logger.debug(f"Promocode '{code}' found")
            return self._to_dto(db_obj)

        logger.debug(f"Promocode '{code}' not found")
        return None

    async def deactivate(self, promocode_id: int) -> None:
        stmt = (
            update(Promocode)
            .where(Promocode.id == promocode_id)
            .values(is_active=False)
        )
        await self.session.execute(stmt)
        logger.debug(f"Promocode id='{promocode_id}' deactivated")

    async def count_activations(self, promocode_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(PromocodeActivation)
            .where(PromocodeActivation.promocode_id == promocode_id)
        )
        count = await self.session.scalar(stmt) or 0
        logger.debug(f"Promocode id='{promocode_id}' has '{count}' activations")
        return int(count)

    async def has_user_activated(self, promocode_id: int, user_telegram_id: int) -> bool:
        stmt = (
            select(func.count())
            .select_from(PromocodeActivation)
            .where(
                PromocodeActivation.promocode_id == promocode_id,
                PromocodeActivation.user_telegram_id == user_telegram_id,
            )
        )
        count = await self.session.scalar(stmt) or 0
        return count > 0

    async def record_activation(
        self,
        activation: PromocodeActivationDto,
    ) -> PromocodeActivationDto:
        db_obj = PromocodeActivation(
            promocode_id=activation.promocode_id,
            user_telegram_id=activation.user_telegram_id,
            transaction_payment_id=activation.transaction_payment_id,
        )
        self.session.add(db_obj)
        await self.session.flush()

        logger.debug(
            f"Recorded activation: promocode_id='{activation.promocode_id}' "
            f"user='{activation.user_telegram_id}'"
        )
        return self._to_activation_dto(db_obj)

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PromocodeDto]:
        stmt = (
            select(Promocode)
            .order_by(Promocode.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.scalars(stmt)
        db_list = cast(list, result.all())

        logger.debug(f"Retrieved '{len(db_list)}' promocodes")
        return self._to_dto_list(db_list)
