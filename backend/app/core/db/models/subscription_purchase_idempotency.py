from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class SubscriptionPurchaseIdempotency(BaseSql, TimestampMixin):
    __tablename__ = "subscription_purchase_idempotency"

    key: Mapped[str] = mapped_column(primary_key=True)
    subscription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(
            "subscriptions.id",
            ondelete="CASCADE",
            name="fk_subscription_purchase_idempotency_subscription_id",
        ),
        index=True,
    )
    # RENEW only: the absolute expiry this purchase writes to the panel, pinned
    # before the panel call so a retry re-applies the same value instead of
    # extending a second time.
    renew_expire_at: Mapped[Optional[datetime]]
