from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import SessionAudience


class UserSession(BaseSql, TimestampMixin):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # the hash the last rotation replaced, kept briefly so a refresh from
    # another tab reads as a race, not theft (RefreshSessionUseCase)
    previous_refresh_token_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    previous_hash_grace_until: Mapped[Optional[datetime]]
    ip_address: Mapped[str] = mapped_column(String(45))  # IPv6-safe length
    user_agent: Mapped[Optional[str]] = mapped_column(String(255))
    last_used_at: Mapped[datetime]
    expires_at: Mapped[datetime] = mapped_column(index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(index=True)
    audience: Mapped[SessionAudience] = mapped_column(
        default=SessionAudience.DASHBOARD, server_default="DASHBOARD"
    )
