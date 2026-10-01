import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.payment_gateway import PaymentGateway
from app.core.enums import PaymentGatewayType
from app.modules.gateways.dto import PaymentGatewayDto
from app.modules.gateways.field_catalog import gateway_flags, is_gateway_configured


class GatewaysRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _default_order_index(self, gateway_type: PaymentGatewayType) -> int:
        return list(PaymentGatewayType).index(gateway_type)

    def _to_dto(self, row: PaymentGateway) -> PaymentGatewayDto:
        values: dict[str, str] = json.loads(row.settings) if row.settings else {}
        return PaymentGatewayDto(
            id=row.id,
            type=row.type,
            order_index=row.order_index,
            is_active=row.is_active,
            is_configured=is_gateway_configured(row.type, values),
            flags=gateway_flags(row.type, values),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _default_dto(self, gateway_type: PaymentGatewayType) -> PaymentGatewayDto:
        return PaymentGatewayDto(
            type=gateway_type,
            order_index=self._default_order_index(gateway_type),
            is_active=False,
            is_configured=is_gateway_configured(gateway_type, {}),
            flags=gateway_flags(gateway_type, {}),
        )

    async def _get_row(self, gateway_type: PaymentGatewayType) -> Optional[PaymentGateway]:
        row: Optional[PaymentGateway] = await self.session.scalar(
            select(PaymentGateway).where(PaymentGateway.type == gateway_type)
        )
        return row

    async def get_all(self) -> list[PaymentGatewayDto]:
        result = await self.session.execute(select(PaymentGateway))
        rows_by_type = {row.type: row for row in result.scalars()}

        dtos = [
            self._to_dto(rows_by_type[gateway_type])
            if gateway_type in rows_by_type
            else self._default_dto(gateway_type)
            for gateway_type in PaymentGatewayType
        ]
        dtos.sort(key=lambda dto: dto.order_index)
        return dtos

    async def get_by_type(self, gateway_type: PaymentGatewayType) -> PaymentGatewayDto:
        row = await self._get_row(gateway_type)
        return self._to_dto(row) if row is not None else self._default_dto(gateway_type)

    async def get_raw_settings(self, gateway_type: PaymentGatewayType) -> dict[str, str]:
        row = await self._get_row(gateway_type)
        return json.loads(row.settings) if row and row.settings else {}

    async def update_settings(
        self, gateway_type: PaymentGatewayType, values: dict[str, str]
    ) -> PaymentGatewayDto:
        row = await self._get_row(gateway_type)
        if row is None:
            row = PaymentGateway(
                type=gateway_type, order_index=self._default_order_index(gateway_type)
            )
            self.session.add(row)

        current: dict[str, str] = json.loads(row.settings) if row.settings else {}
        current.update(values)
        row.settings = json.dumps(current)

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def set_active(
        self, gateway_type: PaymentGatewayType, is_active: bool
    ) -> PaymentGatewayDto:
        row = await self._get_row(gateway_type)
        if row is None:
            row = PaymentGateway(
                type=gateway_type, order_index=self._default_order_index(gateway_type)
            )
            self.session.add(row)

        row.is_active = is_active

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def reorder(self, ordered_types: list[PaymentGatewayType]) -> list[PaymentGatewayDto]:
        result = await self.session.execute(select(PaymentGateway))
        rows_by_type = {row.type: row for row in result.scalars()}

        for index, gateway_type in enumerate(ordered_types):
            row = rows_by_type.get(gateway_type)
            if row is None:
                row = PaymentGateway(type=gateway_type)
                self.session.add(row)
            row.order_index = index

        await self.session.flush()
        result = await self.session.execute(
            select(PaymentGateway).where(PaymentGateway.type.in_(ordered_types))
        )
        refreshed_by_type = {row.type: row for row in result.scalars()}
        return [self._to_dto(refreshed_by_type[gateway_type]) for gateway_type in ordered_types]
