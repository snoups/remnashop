from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import AccessMode


class AccessSettings(BaseSql, TimestampMixin):
    __tablename__ = "access_settings"

    # single row, id=1 (core/db/singleton.py)
    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[AccessMode] = mapped_column(default=AccessMode.PUBLIC, server_default="PUBLIC")
    registration_enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    payments_enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
