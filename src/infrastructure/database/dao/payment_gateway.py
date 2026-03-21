from typing import Optional, cast

from adaptix import Retort
from adaptix.conversion import ConversionRetort
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.common import Cryptographer
from src.application.common.dao import PaymentGatewayDao
from src.application.dto import PaymentGatewayDto
from src.core.enums import PaymentGatewayType
from src.infrastructure.database.models import PaymentGateway

from .base import BaseDaoImpl


class PaymentGatewayDaoImpl(PaymentGatewayDao, BaseDaoImpl):
    def __init__(
        self,
        session: AsyncSession,
        retort: Retort,
        conversion_retort: ConversionRetort,
        redis: Redis,
        cryptographer: Cryptographer,
    ) -> None:
        self.session = session
        self.retort = retort
        self.conversion_retort = conversion_retort
        self.redis = redis
        self.cryptographer = cryptographer

        self._convert_to_dto = self.conversion_retort.get_converter(
            PaymentGateway,
            PaymentGatewayDto,
        )
        self._convert_to_dto_list = self.conversion_retort.get_converter(
            list[PaymentGateway],
            list[PaymentGatewayDto],
        )

    async def create(self, gateway: PaymentGatewayDto) -> PaymentGatewayDto:
        stmt = select(func.max(PaymentGateway.order_index))
        max_index = await self.session.scalar(stmt) or 0

        gateway_data = self.retort.dump(gateway)
        gateway_data["order_index"] = max_index + 1

        db_gateway = PaymentGateway(**gateway_data)
        self.session.add(db_gateway)
        await self.session.flush()

        logger.debug(f"Created payment gateway '{gateway.type}' with index '{max_index + 1}'")
        return self._convert_to_dto(db_gateway)

    async def get_by_id(self, gateway_id: int) -> Optional[PaymentGatewayDto]:
        stmt = select(PaymentGateway).where(PaymentGateway.id == gateway_id)
        db_gateway = await self.session.scalar(stmt)

        if db_gateway:
            logger.debug(f"Payment gateway with id '{gateway_id}' found")
            return self._convert_to_dto(db_gateway)

        logger.debug(f"Payment gateway with id '{gateway_id}' not found")
        return None

    async def get_by_type(self, gateway_type: PaymentGatewayType) -> Optional[PaymentGatewayDto]:
        stmt = select(PaymentGateway).where(PaymentGateway.type == gateway_type)
        db_gateway = await self.session.scalar(stmt)

        if db_gateway:
            logger.debug(f"Payment gateway '{gateway_type}' found")
            return self._convert_to_dto(db_gateway)

        logger.debug(f"Payment gateway '{gateway_type}' not found")
        return None

    async def get_active(self) -> list[PaymentGatewayDto]:
        stmt = (
            select(PaymentGateway)
            .where(PaymentGateway.is_active.is_(True))
            .order_by(PaymentGateway.order_index.asc())
        )
        result = await self.session.scalars(stmt)
        db_gateways = cast(list, result.all())

        logger.debug(f"Retrieved '{len(db_gateways)}' active gateways")
        return self._convert_to_dto_list(db_gateways)

    async def get_all(
        self,
        only_active: bool = False,
        sorted: bool = True,
    ) -> list[PaymentGatewayDto]:
        stmt = select(PaymentGateway)

        if sorted:
            stmt = stmt.order_by(PaymentGateway.order_index.asc())
        else:
            stmt = stmt.order_by(PaymentGateway.id.asc())
        if only_active:
            stmt = stmt.where(PaymentGateway.is_active.is_(True))

        result = await self.session.scalars(stmt)
        db_gateways = cast(list, result.all())

        logger.debug(
            f"Retrieved '{len(db_gateways)}' gateways with only_active status '{only_active}'"
        )
        return self._convert_to_dto_list(db_gateways)

    async def update(self, gateway: PaymentGatewayDto) -> Optional[PaymentGatewayDto]:
        if not gateway.changed_data:
            logger.warning("No changes detected in gateway, skipping update")
            return None

        values_to_update = self._serialize_for_update(
            gateway,
            PaymentGatewayDto,
            PaymentGateway,
            pre_process=self.cryptographer.encrypt_recursive,
        )

        stmt = (
            update(PaymentGateway)
            .where(PaymentGateway.id == gateway.id)
            .values(**values_to_update)
            .returning(PaymentGateway)
        )
        db_settings = await self.session.scalar(stmt)

        if not db_settings:
            logger.warning(f"Failed to update gateway with ID '{gateway.id}': record not found")
            return None

        logger.debug(f"Gateway '{gateway.id}' updated with keys '{list(values_to_update.keys())}'")
        return self._convert_to_dto(db_settings)

    async def set_active_status(self, gateway_type: PaymentGatewayType, is_active: bool) -> None:
        stmt = (
            update(PaymentGateway)
            .where(PaymentGateway.type == gateway_type)
            .values(is_active=is_active)
        )
        await self.session.execute(stmt)
        logger.debug(f"Gateway '{gateway_type}' active status set to '{is_active}'")

    async def count_active(self) -> int:
        stmt = (
            select(func.count())
            .select_from(PaymentGateway)
            .where(PaymentGateway.is_active.is_(True))
        )
        count = await self.session.scalar(stmt) or 0

        logger.debug(f"Total active gateways count is '{count}'")
        return count
