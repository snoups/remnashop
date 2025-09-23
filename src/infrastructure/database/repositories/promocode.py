from typing import Any, Optional

from src.core.enums import PromocodeRewardType
from src.infrastructure.database.models.sql import Promocode

from .base import BaseRepository


class PromocodeRepository(BaseRepository):
    async def create(self, promocode: Promocode) -> Promocode:
        return await self.create_instance(promocode)

    async def get(self, promocode_id: int) -> Optional[Promocode]:
        return await self._get_one(Promocode, Promocode.id == promocode_id)

    async def get_by_code(self, code: str) -> Optional[Promocode]:
        return await self._get_one(Promocode, Promocode.code == code)

    async def get_all(self) -> list[Promocode]:
        return await self._get_many(Promocode)

    async def update(self, promocode_id: int, **data: Any) -> Optional[Promocode]:
        return await self._update(Promocode, Promocode.id == promocode_id, **data)

    async def delete(self, promocode_id: int) -> bool:
        return bool(await self._delete(Promocode, Promocode.id == promocode_id))

    async def filter_by_type(self, promocode_type: PromocodeRewardType) -> list[Promocode]:
        return await self._get_many(Promocode, Promocode.reward_type == promocode_type)

    async def filter_active(self, is_active: bool) -> list[Promocode]:
        return await self._get_many(Promocode, Promocode.is_active == is_active)
