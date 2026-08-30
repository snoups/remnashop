from datetime import datetime
from typing import Any, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.events import EventCategory


class EventLogEntry(BaseSql):
    __tablename__ = "event_log_entries"

    id: Mapped[int] = mapped_column(primary_key=True)

    category: Mapped[EventCategory] = mapped_column(index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    occurred_at: Mapped[datetime] = mapped_column(index=True)

    # Snapshot at the time of the event, not a live join -- demote_admin clears
    # login/password_hash, so resolving the actor's name via a live join would
    # turn a historical "Ivan created an admin" row into "null created an admin"
    # once Ivan himself gets demoted. actor_id is kept too for programmatic joins.
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_login: Mapped[Optional[str]] = mapped_column(String(64))
    actor_name: Mapped[Optional[str]] = mapped_column(String())
    actor_email: Mapped[Optional[str]] = mapped_column(String())

    ip_address: Mapped[Optional[str]] = mapped_column(String(45))

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
