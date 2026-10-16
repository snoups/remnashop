from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import DEFAULT_ALLOWED_EMAIL_DOMAINS
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
    restrict_email_domains: Mapped[bool] = mapped_column(default=True, server_default="true")
    allowed_email_domains: Mapped[list[str]] = mapped_column(
        JSONB, default=lambda: list(DEFAULT_ALLOWED_EMAIL_DOMAINS), server_default="[]"
    )
