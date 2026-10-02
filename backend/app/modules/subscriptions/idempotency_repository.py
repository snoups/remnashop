from datetime import datetime
from typing import Optional, cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.addon_grant_idempotency import AddOnGrantIdempotency
from app.core.db.models.subscription_purchase_idempotency import SubscriptionPurchaseIdempotency


class PurchaseIdempotencyRepository:
    """Keys that make a purchase or add-on grant land once across retries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim(self, key: str) -> bool:
        result = await self.session.execute(
            pg_insert(SubscriptionPurchaseIdempotency)
            .values(key=key, subscription_id=None)
            .on_conflict_do_nothing(index_elements=["key"])
            .returning(SubscriptionPurchaseIdempotency.key)
        )
        claimed = result.scalar_one_or_none() is not None
        await self.session.flush()
        return claimed

    async def get_subscription_id(self, key: str) -> Optional[int]:
        row = await self.session.get(SubscriptionPurchaseIdempotency, key)
        return row.subscription_id if row is not None else None

    async def link(self, key: str, subscription_id: int) -> None:
        row = await self.session.get(SubscriptionPurchaseIdempotency, key)
        if row is not None:
            row.subscription_id = subscription_id
            await self.session.flush()

    async def get_pending_renew_expire_at(self, key: str) -> Optional[datetime]:
        row = await self.session.get(SubscriptionPurchaseIdempotency, key)
        if row is None or row.subscription_id is not None:
            return None
        return row.renew_expire_at

    async def pin_renew_expire_at(self, key: str, expire_at: datetime) -> None:
        row = await self.session.get(SubscriptionPurchaseIdempotency, key)
        if row is not None:
            row.renew_expire_at = expire_at
            await self.session.flush()

    async def lock(self, key: str) -> Optional[int]:
        """Serializes completion of one purchase; returns its subscription id if
        another attempt already finished it."""
        row = await self.session.scalar(
            select(SubscriptionPurchaseIdempotency)
            .where(SubscriptionPurchaseIdempotency.key == key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return row.subscription_id if row is not None else None

    async def release(self, key: str) -> None:
        row = await self.session.get(SubscriptionPurchaseIdempotency, key)
        if row is not None:
            await self.session.delete(row)
            await self.session.flush()

    async def delete_stale(self, cutoff: datetime) -> tuple[int, int]:
        purchase = await self.session.execute(
            delete(SubscriptionPurchaseIdempotency).where(
                SubscriptionPurchaseIdempotency.created_at < cutoff
            )
        )
        addon = await self.session.execute(
            delete(AddOnGrantIdempotency).where(AddOnGrantIdempotency.created_at < cutoff)
        )
        return cast(CursorResult, purchase).rowcount, cast(CursorResult, addon).rowcount
