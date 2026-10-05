from typing import Any, Optional

from sqlalchemy import Boolean, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class LoyaltySettings(BaseSql, TimestampMixin):
    __tablename__ = "loyalty_settings"

    # single row, id=1 (core/db/singleton.py)
    id: Mapped[int] = mapped_column(primary_key=True)

    enabled: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
    # NULL = all time
    window_months: Mapped[Optional[int]] = mapped_column(SmallInteger())
    # [{"threshold": "1000.00", "percent": 3}, ...] in the anchor currency; saved as one bundle
    tiers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB(), default=list)
