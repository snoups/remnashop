from datetime import datetime
from typing import Any, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.events import EventCategory


class EventOutboxEntry(BaseSql):
    __tablename__ = "event_outbox"

    id: Mapped[int] = mapped_column(primary_key=True)

    category: Mapped[EventCategory] = mapped_column(index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    occurred_at: Mapped[datetime]

    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_login: Mapped[Optional[str]] = mapped_column(String(64))
    actor_name: Mapped[Optional[str]] = mapped_column(String())
    actor_email: Mapped[Optional[str]] = mapped_column(String())

    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)

    processed_at: Mapped[Optional[datetime]] = mapped_column(index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[Optional[str]] = mapped_column(String())
