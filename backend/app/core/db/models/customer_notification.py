from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class CustomerNotification(BaseSql, TimestampMixin):
    """One entry of the customer's cabinet feed (the bell)."""

    __tablename__ = "customer_notifications"
    __table_args__ = (UniqueConstraint("user_id", "outbox_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # the outbox event it came from: a redelivered task must not add it twice
    outbox_id: Mapped[int]
    event_type: Mapped[str] = mapped_column(String(128))
    args: Mapped[dict[str, Any]] = mapped_column(JSONB)
    subscription_id: Mapped[Optional[int]]
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
