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

    # Snapshot, not a live join: demote_admin clears the login, so a join would
    # turn "Ivan created an admin" into "null created an admin" once Ivan is
    # demoted. actor_id stays for joins.
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_login: Mapped[Optional[str]] = mapped_column(String(64))
    actor_name: Mapped[Optional[str]] = mapped_column(String())
    actor_email: Mapped[Optional[str]] = mapped_column(String())

    ip_address: Mapped[Optional[str]] = mapped_column(String(45))

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)

    # a retried outbox dispatch upserts on it instead of writing a second
    # audit-log row; NULL for a row that never came through the outbox
    outbox_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("event_outbox.id", ondelete="SET NULL"), unique=True, nullable=True
    )

    # the account the event was about (ActorTargetEvent's target); a column, not a
    # payload lookup, since a user's card filters the log by it
    target_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
