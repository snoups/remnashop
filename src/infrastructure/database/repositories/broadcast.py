from typing import Any, Optional
from uuid import UUID

from sqlalchemy import update

from src.infrastructure.database.models.sql import Broadcast, BroadcastMessage

from .base import BaseRepository


class BroadcastRepository(BaseRepository):
    async def create(self, broadcast: Broadcast) -> Broadcast:
        return await self.create_instance(broadcast)

    async def create_messages(self, messages: list[BroadcastMessage]) -> list[BroadcastMessage]:
        return await self.create_instances(messages)

    async def get(self, task_id: UUID) -> Optional[Broadcast]:
        return await self._get_one(Broadcast, Broadcast.task_id == task_id)

    async def get_all(self) -> list[Broadcast]:
        return await self._get_many(Broadcast, order_by=Broadcast.id.asc())

    async def get_message_by_user(
        self, broadcast_id: int, user_id: int
    ) -> Optional[BroadcastMessage]:
        return await self._get_one(
            BroadcastMessage,
            BroadcastMessage.broadcast_id == broadcast_id,
            BroadcastMessage.user_id == user_id,
        )

    async def update(self, task_id: UUID, **data: Any) -> Optional[Broadcast]:
        return await self._update(Broadcast, Broadcast.task_id == task_id, **data)

    async def update_message(
        self, broadcast_id: int, user_id: int, **data: Any
    ) -> Optional[BroadcastMessage]:
        return await self._update(
            BroadcastMessage,
            BroadcastMessage.broadcast_id == broadcast_id,
            BroadcastMessage.user_id == user_id,
            **data,
        )

    async def bulk_update_messages(self, data: list[dict]) -> None:
        if not data:
            return

        await self.session.execute(update(BroadcastMessage), data)
