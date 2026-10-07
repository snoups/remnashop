from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import NOW_FUNC, TimestampMixin


class PushSubscription(BaseSql, TimestampMixin):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # the session that subscribed: the device stops getting alerts once it's
    # revoked or expired, and the row goes when auth prunes the session
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user_sessions.id", ondelete="CASCADE"), index=True
    )
    # one browser = one endpoint; it belongs to whoever is signed in there now
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))
    failure_count: Mapped[int] = mapped_column(default=0, server_default="0")
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=NOW_FUNC, nullable=False
    )
