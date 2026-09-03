from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.addon import AddOn
from app.core.db.models.addon_price_override import AddOnPriceOverride
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.subscriptions.dto import (
    AddOnDto,
    AddOnPriceOverrideDto,
    CreateAddOnDto,
    ReorderAddOnsDto,
    SetAddOnBasePriceDto,
    SetAddOnPriceOverrideDto,
    UpdateAddOnDto,
)


class AddOnRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _load_overrides(self, addon_ids: list[int]) -> dict[int, list[AddOnPriceOverrideDto]]:
        if not addon_ids:
            return {}

        result = await self.session.execute(
            select(AddOnPriceOverride)
            .where(AddOnPriceOverride.addon_id.in_(addon_ids))
            .order_by(AddOnPriceOverride.id)
        )
        overrides_by_addon: dict[int, list[AddOnPriceOverrideDto]] = {}
        for row in result.scalars():
            overrides_by_addon.setdefault(row.addon_id, []).append(
                AddOnPriceOverrideDto(currency=row.currency, price=row.price)
            )
        return overrides_by_addon

    def _to_dto(self, row: AddOn, overrides: list[AddOnPriceOverrideDto]) -> AddOnDto:
        return AddOnDto(
            id=row.id,
            name=row.name,
            type=row.type,
            amount=row.amount,
            order_index=row.order_index,
            is_active=row.is_active,
            base_price=row.base_price,
            overrides=overrides,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def _get_or_raise(self, addon_id: int) -> AddOn:
        row = await self.session.get(AddOn, addon_id)
        if row is None:
            raise NotFoundError(f"AddOn '{addon_id}' not found")
        return row

    async def get_by_id(self, addon_id: int) -> AddOnDto:
        row = await self._get_or_raise(addon_id)
        overrides_by_addon = await self._load_overrides([row.id])
        return self._to_dto(row, overrides_by_addon.get(row.id, []))

    async def list_all(self) -> list[AddOnDto]:
        result = await self.session.execute(select(AddOn).order_by(AddOn.order_index, AddOn.id))
        rows = result.scalars().all()
        overrides_by_addon = await self._load_overrides([row.id for row in rows])
        return [self._to_dto(row, overrides_by_addon.get(row.id, [])) for row in rows]

    async def create(self, data: CreateAddOnDto) -> AddOnDto:
        count_result = await self.session.execute(select(func.count()).select_from(AddOn))
        next_order_index = count_result.scalar_one()

        row = AddOn(
            name=data.name,
            type=data.type,
            amount=data.amount,
            base_price=data.base_price,
            order_index=next_order_index,
            is_active=False,
        )
        self.session.add(row)

        try:
            await self.session.flush()
        except IntegrityError as error:
            raise ConflictError(f"AddOn with name '{data.name}' already exists") from error

        await self.session.refresh(row)
        return self._to_dto(row, [])

    async def update(self, data: UpdateAddOnDto) -> AddOnDto:
        row = await self._get_or_raise(data.addon_id)

        if data.name is not None:
            row.name = data.name
        if data.type is not None:
            row.type = data.type
        if data.amount is not None:
            row.amount = data.amount
        if data.is_active is not None:
            row.is_active = data.is_active

        try:
            await self.session.flush()
        except IntegrityError as error:
            raise ConflictError(f"AddOn name '{data.name}' already exists") from error

        await self.session.refresh(row)
        overrides_by_addon = await self._load_overrides([row.id])
        return self._to_dto(row, overrides_by_addon.get(row.id, []))

    async def delete(self, addon_id: int) -> None:
        await self._get_or_raise(addon_id)
        try:
            await self.session.execute(delete(AddOn).where(AddOn.id == addon_id))
            await self.session.flush()
        except IntegrityError as error:
            raise ConflictError(f"AddOn '{addon_id}' is still referenced by a promocode") from error

    async def set_base_price(self, data: SetAddOnBasePriceDto) -> AddOnDto:
        row = await self._get_or_raise(data.addon_id)
        row.base_price = data.base_price

        await self.session.flush()
        await self.session.refresh(row)
        overrides_by_addon = await self._load_overrides([row.id])
        return self._to_dto(row, overrides_by_addon.get(row.id, []))

    async def set_price_override(self, data: SetAddOnPriceOverrideDto) -> AddOnDto:
        if data.price is not None and data.currency == data.anchor:
            raise ValidationError("Cannot override the anchor currency's price")

        row = await self._get_or_raise(data.addon_id)

        if data.price is None:
            await self.session.execute(
                delete(AddOnPriceOverride).where(
                    AddOnPriceOverride.addon_id == data.addon_id,
                    AddOnPriceOverride.currency == data.currency,
                )
            )
        else:
            override_result = await self.session.execute(
                select(AddOnPriceOverride).where(
                    AddOnPriceOverride.addon_id == data.addon_id,
                    AddOnPriceOverride.currency == data.currency,
                )
            )
            override_row = override_result.scalar_one_or_none()
            if override_row is None:
                self.session.add(
                    AddOnPriceOverride(
                        addon_id=data.addon_id, currency=data.currency, price=data.price
                    )
                )
            else:
                override_row.price = data.price

        await self.session.flush()
        overrides_by_addon = await self._load_overrides([row.id])
        return self._to_dto(row, overrides_by_addon.get(row.id, []))

    async def set_base_prices(self, values: dict[int, Decimal]) -> None:
        for addon_id, base_price in values.items():
            row = await self.session.get(AddOn, addon_id)
            if row is None:
                raise NotFoundError(f"AddOn '{addon_id}' not found")
            row.base_price = base_price
        await self.session.flush()

    async def reorder(self, data: ReorderAddOnsDto) -> list[AddOnDto]:
        result = await self.session.execute(select(AddOn))
        rows = {row.id: row for row in result.scalars()}

        if set(data.addon_ids) != set(rows):
            raise ValidationError("Reorder must include every existing addon id exactly once")

        for index, addon_id in enumerate(data.addon_ids):
            rows[addon_id].order_index = index

        await self.session.flush()
        return await self.list_all()
