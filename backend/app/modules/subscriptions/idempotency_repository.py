from datetime import datetime, timedelta
from typing import Final, Optional, cast

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.addon_grant_idempotency import AddOnGrantIdempotency
from app.core.db.models.subscription_purchase_idempotency import SubscriptionPurchaseIdempotency
from app.core.db.timestamp import NOW_FUNC
from app.core.error_codes import ErrorCode
from app.modules.subscriptions.domain import SupersededError

# Must exceed the longest webhook-resend window of any payment provider --
# deleting a still-resendable key turns a replay into a fresh claim (double
# charge + double provisioning).
IDEMPOTENCY_KEY_RETENTION_DAYS: Final[int] = 7


def _claim_lost(key: str) -> SupersededError:
    return SupersededError(
        f"Purchase claim '{key}' was taken over by another attempt",
        code=ErrorCode.PURCHASE_SUPERSEDED,
    )


class PurchaseIdempotencyRepository:
    """Keys that make a purchase or add-on grant land once across retries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim(self, key: str, *, stale_after: timedelta) -> Optional[datetime]:
        """Returns the claim's token (its created_at), or None when another attempt holds it."""
        inserted = await self.session.execute(
            pg_insert(SubscriptionPurchaseIdempotency)
            .values(key=key, subscription_id=None)
            .on_conflict_do_nothing(index_elements=["key"])
            .returning(SubscriptionPurchaseIdempotency.created_at)
        )
        token = inserted.scalar_one_or_none()
        if token is None:
            # an attempt killed mid-purchase never released its key; the database
            # clock decides staleness, so app clock skew can't reclaim a live claim
            reclaimed = await self.session.execute(
                update(SubscriptionPurchaseIdempotency)
                .where(
                    SubscriptionPurchaseIdempotency.key == key,
                    SubscriptionPurchaseIdempotency.subscription_id.is_(None),
                    SubscriptionPurchaseIdempotency.renew_expire_at.is_(None),
                    SubscriptionPurchaseIdempotency.created_at < NOW_FUNC - stale_after,
                )
                .values(created_at=NOW_FUNC)
                .returning(SubscriptionPurchaseIdempotency.created_at)
            )
            token = reclaimed.scalar_one_or_none()
        await self.session.flush()
        return token

    async def get_claim_token(self, key: str) -> Optional[datetime]:
        token: Optional[datetime] = await self.session.scalar(
            select(SubscriptionPurchaseIdempotency.created_at).where(
                SubscriptionPurchaseIdempotency.key == key
            )
        )
        return token

    async def get_subscription_id(self, key: str) -> Optional[int]:
        row = await self.session.get(SubscriptionPurchaseIdempotency, key)
        return row.subscription_id if row is not None else None

    async def link(self, key: str, subscription_id: int, token: Optional[datetime]) -> None:
        result = await self.session.execute(
            update(SubscriptionPurchaseIdempotency)
            .where(
                SubscriptionPurchaseIdempotency.key == key,
                SubscriptionPurchaseIdempotency.created_at == token,
            )
            .values(subscription_id=subscription_id)
            .execution_options(synchronize_session=False)
        )
        if cast(CursorResult, result).rowcount == 0:
            raise _claim_lost(key)
        await self.session.flush()

    async def get_pending_renew_expire_at(self, key: str) -> Optional[datetime]:
        row = await self.session.get(SubscriptionPurchaseIdempotency, key)
        if row is None or row.subscription_id is not None:
            return None
        return row.renew_expire_at

    async def pin_renew_expire_at(
        self, key: str, expire_at: datetime, token: Optional[datetime]
    ) -> None:
        # pinned before the panel write: an attempt that lost its claim must not write at all
        result = await self.session.execute(
            update(SubscriptionPurchaseIdempotency)
            .where(
                SubscriptionPurchaseIdempotency.key == key,
                SubscriptionPurchaseIdempotency.created_at == token,
                SubscriptionPurchaseIdempotency.subscription_id.is_(None),
            )
            .values(renew_expire_at=expire_at)
            .execution_options(synchronize_session=False)
        )
        if cast(CursorResult, result).rowcount == 0:
            raise _claim_lost(key)
        await self.session.flush()

    async def lock(self, key: str, token: Optional[datetime]) -> Optional[int]:
        """Serializes completion of one purchase; returns its subscription id if
        another attempt already finished it, refuses if this attempt lost its claim."""
        row = await self.session.scalar(
            select(SubscriptionPurchaseIdempotency)
            .where(SubscriptionPurchaseIdempotency.key == key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is not None and row.subscription_id is not None:
            return row.subscription_id
        if row is None or row.created_at != token:
            raise _claim_lost(key)
        return None

    async def release(self, key: str, token: datetime) -> None:
        # a linked key belongs to a finished purchase: an attempt that failed after
        # reclaiming it must not erase that link
        await self.session.execute(
            delete(SubscriptionPurchaseIdempotency).where(
                SubscriptionPurchaseIdempotency.key == key,
                SubscriptionPurchaseIdempotency.subscription_id.is_(None),
                SubscriptionPurchaseIdempotency.created_at == token,
            )
        )
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
