from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class SubscriptionPurchaseIdempotency(BaseSql, TimestampMixin):
    __tablename__ = "subscription_purchase_idempotency"

    key: Mapped[str] = mapped_column(primary_key=True)
    subscription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True
    )
