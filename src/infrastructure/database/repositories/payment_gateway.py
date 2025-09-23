from typing import Any, Optional

from src.core.enums import PaymentGatewayType
from src.infrastructure.database.models.sql import PaymentGateway

from .base import BaseRepository


class PaymentGatewayRepository(BaseRepository):
    async def get(self, gateway_id: int) -> Optional[PaymentGateway]:
        return await self._get_one(PaymentGateway, PaymentGateway.id == gateway_id)

    async def get_by_type(self, gateway_type: PaymentGatewayType) -> Optional[PaymentGateway]:
        return await self._get_one(PaymentGateway, PaymentGateway.type == gateway_type)

    async def get_all(self) -> list[PaymentGateway]:
        return await self._get_many(PaymentGateway, order_by=PaymentGateway.id.asc())

    async def update(self, gateway_id: int, **data: Any) -> Optional[PaymentGateway]:
        return await self._update(PaymentGateway, PaymentGateway.id == gateway_id, **data)

    async def filter_active(self, is_active: bool) -> list[PaymentGateway]:
        return await self._get_many(PaymentGateway, PaymentGateway.is_active == is_active)
