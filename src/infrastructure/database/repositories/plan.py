from typing import Optional

from src.core.enums import PlanAvailability, PlanType
from src.infrastructure.database.models.sql import Plan

from .base import BaseRepository


class PlanRepository(BaseRepository):
    async def create(self, plan: Plan) -> Plan:
        return await self.create_instance(plan)

    async def get(self, plan_id: int) -> Optional[Plan]:
        return await self._get_one(Plan, Plan.id == plan_id)

    async def get_by_name(self, name: str) -> Optional[Plan]:
        return await self._get_one(Plan, Plan.name == name)

    async def get_all(self) -> list[Plan]:
        return await self._get_many(Plan)

    async def update(self, plan: Plan) -> Optional[Plan]:
        return await self.merge_instance(plan)

    async def delete(self, plan_id: int) -> bool:
        return bool(await self._delete(Plan, Plan.id == plan_id))

    async def filter_by_type(self, plan_type: PlanType) -> list[Plan]:
        return await self._get_many(Plan, Plan.type == plan_type)

    async def filter_by_availability(self, availability: PlanAvailability) -> list[Plan]:
        return await self._get_many(Plan, Plan.availability == availability)

    async def filter_active(self, is_active: bool) -> list[Plan]:
        return await self._get_many(Plan, Plan.is_active == is_active)
