from typing import Optional

from adaptix import Retort
from adaptix.conversion import ConversionRetort
from loguru import logger
from sqlalchemy import delete, func, select, update
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

        self._convert_to_dto = self.conversion_retort.get_converter(Promocode, PromocodeDto)
        self._convert_activation_to_dto = self.conversion_retort.get_converter(
            PromocodeActivation,
            PromocodeActivationDto,
        )

    async def create(self, promocode: PromocodeDto) -> PromocodeDto:
        promocode_data = self.retort.dump(promocode)
        for key in ("id", "created_at", "updated_at"):
            promocode_data.pop(key, None)

        db_promocode = Promocode(**promocode_data)
        self.session.add(db_promocode)
        await self.session.flush()

        logger.debug(f"Created promocode '{promocode.code}'")
        return self._convert_to_dto(db_promocode)

    async def get_by_id(self, promocode_id: int) -> Optional[PromocodeDto]:
        stmt = select(Promocode).where(Promocode.id == promocode_id)
        db_promocode = await self.session.scalar(stmt)

        if not db_promocode:
            logger.debug(f"Promocode '{promocode_id}' not found")
            return None

        logger.debug(f"Promocode '{promocode_id}' found")
        return self._convert_to_dto(db_promocode)

    async def get_by_code(self, code: str) -> Optional[PromocodeDto]:
        normalized_code = code.strip().upper()
        stmt = select(Promocode).where(func.upper(Promocode.code) == normalized_code)
        db_promocode = await self.session.scalar(stmt)

        if not db_promocode:
            logger.debug(f"Promocode '{normalized_code}' not found")
            return None

        logger.debug(f"Promocode '{normalized_code}' found")
        return self._convert_to_dto(db_promocode)

    async def get_all(self) -> list[PromocodeDto]:
        stmt = select(Promocode).order_by(Promocode.id.desc())
        result = await self.session.scalars(stmt)
        db_promocodes = list(result.all())

        logger.debug(f"Loaded '{len(db_promocodes)}' promocode(s)")
        return [self._convert_to_dto(promocode) for promocode in db_promocodes]

    async def update(self, promocode: PromocodeDto) -> Optional[PromocodeDto]:
        if promocode.id is None:
            raise ValueError("Promocode id is required for update")

        changed_data = promocode.changed_data.copy()
        changed_data.pop("created_at", None)
        changed_data.pop("updated_at", None)

        if not changed_data:
            return await self.get_by_id(promocode.id)

        stmt = (
            update(Promocode)
            .where(Promocode.id == promocode.id)
            .values(**changed_data)
            .returning(Promocode)
        )
        db_promocode = await self.session.scalar(stmt)

        if not db_promocode:
            logger.warning(f"Failed to update promocode '{promocode.id}'")
            return None

        logger.debug(f"Updated promocode '{promocode.id}' with '{changed_data}'")
        return self._convert_to_dto(db_promocode)

    async def delete(self, promocode_id: int) -> bool:
        await self.session.execute(
            delete(PromocodeActivation).where(PromocodeActivation.promocode_id == promocode_id)
        )

        stmt = delete(Promocode).where(Promocode.id == promocode_id).returning(Promocode.id)
        result = await self.session.execute(stmt)
        deleted_id = result.scalar_one_or_none()

        if not deleted_id:
            logger.debug(f"Promocode '{promocode_id}' not found for deletion")
            return False

        logger.debug(f"Deleted promocode '{promocode_id}'")
        return True

    async def count_activations(self, promocode_id: int) -> int:
        stmt = (
            select(func.count(PromocodeActivation.id))
            .select_from(PromocodeActivation)
            .where(PromocodeActivation.promocode_id == promocode_id)
        )
        activations = await self.session.scalar(stmt) or 0
        logger.debug(f"Promocode '{promocode_id}' has '{activations}' activation(s)")
        return activations

    async def is_activated_by_user(self, promocode_id: int, user_telegram_id: int) -> bool:
        stmt = select(
            select(PromocodeActivation)
            .where(
                PromocodeActivation.promocode_id == promocode_id,
                PromocodeActivation.user_telegram_id == user_telegram_id,
            )
            .exists()
        )
        is_activated = await self.session.scalar(stmt) or False
        logger.debug(
            f"Promocode '{promocode_id}' activation by user '{user_telegram_id}' is '{is_activated}'"
        )
        return is_activated

    async def create_activation(self, activation: PromocodeActivationDto) -> PromocodeActivationDto:
        activation_data = self.retort.dump(activation)
        activation_data.pop("id", None)
        if activation_data.get("activated_at") is None:
            activation_data.pop("activated_at", None)
        db_activation = PromocodeActivation(**activation_data)

        self.session.add(db_activation)
        await self.session.flush()

        logger.debug(
            f"Created activation for promocode '{activation.promocode_id}' "
            f"and user '{activation.user_telegram_id}'"
        )
        return self._convert_activation_to_dto(db_activation)
