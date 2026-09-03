from datetime import datetime
from typing import Optional

from sqlalchemy import ARRAY, BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class BlacklistSource(BaseSql, TimestampMixin):
    __tablename__ = "blacklist_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[Optional[str]] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True, server_default="true")

    # Fetched from `url`, normalised, replaced wholesale on each sync.
    blocked_telegram_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), server_default="{}")
    blocked_emails: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")

    last_synced_at: Mapped[Optional[datetime]]
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    entries_count: Mapped[int] = mapped_column(default=0, server_default="0")
