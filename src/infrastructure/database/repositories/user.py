from typing import Any, Optional

from sqlalchemy import func, or_

from src.core.enums import UserRole
from src.infrastructure.database.models.sql import User

from .base import BaseRepository


class UserRepository(BaseRepository):
    async def create(self, user: User) -> User:
        return await self.create_instance(user)

    async def get(self, telegram_id: int) -> Optional[User]:
        return await self._get_one(User, User.telegram_id == telegram_id)

    async def get_by_ids(self, telegram_ids: list[int]) -> list[User]:
        return await self._get_many(User, User.telegram_id.in_(telegram_ids))

    async def get_by_partial_name(self, query: str) -> list[User]:
        search_pattern = f"%{query.lower()}%"
        conditions = [
            func.lower(User.name).like(search_pattern),
            func.lower(User.username).like(search_pattern),
        ]
        return await self._get_many(User, or_(*conditions))

    async def get_all(self) -> list[User]:
        return await self._get_many(User)

    async def update(self, telegram_id: int, **data: Any) -> Optional[User]:
        return await self._update(User, User.telegram_id == telegram_id, **data)

    async def delete(self, telegram_id: int) -> bool:
        return bool(await self._delete(User, User.telegram_id == telegram_id))

    async def count(self) -> int:
        return await self._count(User)

    async def filter_by_role(self, role: UserRole) -> list[User]:
        return await self._get_many(User, User.role == role)

    async def filter_by_blocked(self, blocked: bool) -> list[User]:
        return await self._get_many(User, User.is_blocked == blocked)
