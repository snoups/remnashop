from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.encrypted_string import EncryptedString
from app.core.db.timestamp import TimestampMixin
from app.core.enums import SmtpSecurity


class EmailSettings(BaseSql, TimestampMixin):
    __tablename__ = "email_settings"

    # single row, id=1 (core/db/singleton.py)
    id: Mapped[int] = mapped_column(primary_key=True)
    host: Mapped[Optional[str]] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(default=587, server_default="587")
    security: Mapped[SmtpSecurity] = mapped_column(
        default=SmtpSecurity.STARTTLS, server_default="STARTTLS"
    )
    username: Mapped[Optional[str]] = mapped_column(String(255))
    password: Mapped[Optional[str]] = mapped_column(EncryptedString())
    from_address: Mapped[Optional[str]] = mapped_column(String(255))
    from_name: Mapped[Optional[str]] = mapped_column(String(100))
