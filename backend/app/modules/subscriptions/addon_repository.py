from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.addon import AddOn
from app.core.db.models.addon_price import AddOnPrice
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.subscriptions.dto import (
    AddOnDto,
    AddOnPriceDto,
    CreateAddOnDto,
    ReorderAddOnsDto,
    SetAddOnPricesDto,
    UpdateAddOnDto,
)


class AddOnRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _load_prices(self, addon_ids: list[int]) -> dict[int, list[AddOnPriceDto]]:
        if not addon_ids:
            return {}

        result = await self.session.execute(
            select(AddOnPrice).where(AddOnPrice.addon_id.in_(addon_ids)).order_by(AddOnPrice.id)
        )
        prices_by_addon: dict[int, list[AddOnPriceDto]] = {}
        for row in result.scalars():
            prices_by_addon.setdefault(row.addon_id, []).append(
                AddOnPriceDto(currency=row.currency, price=row.price)
            )
        return prices_by_addon

    def _to_dto(self, row: AddOn, prices: list[AddOnPriceDto]) -> AddOnDto:
        return AddOnDto(
            id=row.id,
            name=row.name,
            type=row.type,
            amount=row.amount,
            order_index=row.order_index,
            is_active=row.is_active,
            prices=prices,
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
        prices_by_addon = await self._load_prices([row.id])
        return self._to_dto(row, prices_by_addon.get(row.id, []))

    async def list_all(self) -> list[AddOnDto]:
        result = await self.session.execute(select(AddOn).order_by(AddOn.order_index, AddOn.id))
        rows = result.scalars().all()
        prices_by_addon = await self._load_prices([row.id for row in rows])
        return [self._to_dto(row, prices_by_addon.get(row.id, [])) for row in rows]

    async def create(self, data: CreateAddOnDto) -> AddOnDto:
        count_result = await self.session.execute(select(func.count()).select_from(AddOn))
        next_order_index = count_result.scalar_one()

        row = AddOn(
            name=data.name,
            type=data.type,
            amount=data.amount,
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
        prices_by_addon = await self._load_prices([row.id])
        return self._to_dto(row, prices_by_addon.get(row.id, []))

    async def delete(self, addon_id: int) -> None:
        await self._get_or_raise(addon_id)
        try:
            await self.session.execute(delete(AddOn).where(AddOn.id == addon_id))
            await self.session.flush()
        except IntegrityError as error:
            raise ConflictError(f"AddOn '{addon_id}' is still referenced by a promocode") from error

    async def set_prices(self, data: SetAddOnPricesDto) -> AddOnDto:
        row = await self._get_or_raise(data.addon_id)

        await self.session.execute(delete(AddOnPrice).where(AddOnPrice.addon_id == data.addon_id))
        await self.session.flush()

        for price in data.prices:
            self.session.add(
                AddOnPrice(addon_id=data.addon_id, currency=price.currency, price=price.price)
            )

        await self.session.flush()
        prices_by_addon = await self._load_prices([row.id])
        return self._to_dto(row, prices_by_addon.get(row.id, []))

    async def reorder(self, data: ReorderAddOnsDto) -> list[AddOnDto]:
        result = await self.session.execute(select(AddOn))
        rows = {row.id: row for row in result.scalars()}

        if set(data.addon_ids) != set(rows):
            raise ValidationError("Reorder must include every existing addon id exactly once")

        for index, addon_id in enumerate(data.addon_ids):
            rows[addon_id].order_index = index

        await self.session.flush()
        return await self.list_all()
