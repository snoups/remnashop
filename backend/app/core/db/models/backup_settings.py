from sqlalchemy import Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class BackupSettings(BaseSql, TimestampMixin):
    __tablename__ = "backup_settings"

    # Single row, always id=1 -- same pattern as BotSettings.
    id: Mapped[int] = mapped_column(primary_key=True)

    enabled: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
    interval_hours: Mapped[int] = mapped_column(default=24, server_default="24")
    max_files: Mapped[int] = mapped_column(default=7, server_default="7")
