from typing import Any, Optional

from src.infrastructure.database.models.sql import Subscription

from .base import BaseRepository


class SubscriptionRepository(BaseRepository):
    async def create(self, subscription: Subscription) -> Subscription:
        return await self.create_instance(subscription)

    async def get_by_user(self, telegram_id: int) -> Optional[Subscription]:
        return await self._get_one(Subscription, Subscription.user_telegram_id == telegram_id)

    async def get_all(self) -> list[Subscription]:
        return await self._get_many(Subscription)

    async def update(self, subscription_id: int, **data: Any) -> Optional[Subscription]:
        return await self._update(Subscription, Subscription.id == subscription_id, **data)
