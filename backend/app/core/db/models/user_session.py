from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class UserSession(BaseSql, TimestampMixin):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # The hash rotation just replaced -- kept briefly so a same-moment refresh
    # from another browser tab can be recognized as a benign race, not theft.
    # See RefreshSessionUseCase (Task 8) and the design spec's grace-window section.
    previous_refresh_token_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    previous_hash_grace_until: Mapped[Optional[datetime]]
    ip_address: Mapped[str] = mapped_column(String(45))  # IPv6-safe length
    user_agent: Mapped[Optional[str]] = mapped_column(String(255))
    last_used_at: Mapped[datetime]
    expires_at: Mapped[datetime] = mapped_column(index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(index=True)
