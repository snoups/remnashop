from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class CabinetAuthSettings(BaseSql, TimestampMixin):
    __tablename__ = "cabinet_auth_settings"

    # single row, id=1 (core/db/singleton.py)
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_enabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    google_enabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    yandex_enabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    email_enabled: Mapped[bool] = mapped_column(default=False, server_default="false")
