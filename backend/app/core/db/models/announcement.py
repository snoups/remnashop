from datetime import datetime
from typing import Any, Optional

from sqlalchemy import ARRAY, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class Announcement(BaseSql, TimestampMixin):
    __tablename__ = "announcements"

    # id from the maintainer feed; the feed is mirrored wholesale on each sync
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    notify_at: Mapped[datetime] = mapped_column(index=True)
    roles: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(16)))
    versions: Mapped[Optional[str]] = mapped_column(String(200))
    auto_open: Mapped[bool]
    # icon, severity, title, text, url, slides -- an external format passed through, never queried
    content: Mapped[dict[str, Any]]


class AnnouncementView(BaseSql):
    __tablename__ = "announcement_views"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    announcement_id: Mapped[str] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"), primary_key=True
    )
    seen_at: Mapped[datetime]
    # cleared from the bell before the 24h window ran out
    dismissed_at: Mapped[Optional[datetime]]
