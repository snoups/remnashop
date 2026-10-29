from typing import Any, Optional

from sqlalchemy import Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class ConnectGuideSettings(BaseSql, TimestampMixin):
    __tablename__ = "connect_guide_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    enabled: Mapped[bool] = mapped_column(Boolean(), default=True, server_default="true")
    # the platform → app → step catalog, saved and read as one bundle; NULL = the built-in default
    catalog: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB())
