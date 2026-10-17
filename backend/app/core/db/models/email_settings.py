from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.encrypted_string import EncryptedString
from app.core.db.timestamp import TimestampMixin
from app.core.enums import SmtpSecurity


class EmailSettings(BaseSql, TimestampMixin):
    __tablename__ = "email_settings"

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
    bulk_host: Mapped[Optional[str]] = mapped_column(String(255))
    bulk_port: Mapped[int] = mapped_column(default=587, server_default="587")
    bulk_security: Mapped[SmtpSecurity] = mapped_column(
        default=SmtpSecurity.STARTTLS, server_default="STARTTLS"
    )
    bulk_username: Mapped[Optional[str]] = mapped_column(String(255))
    bulk_password: Mapped[Optional[str]] = mapped_column(EncryptedString())
    bulk_from_address: Mapped[Optional[str]] = mapped_column(String(255))
    bulk_from_name: Mapped[Optional[str]] = mapped_column(String(100))
    bulk_rate_per_minute: Mapped[int] = mapped_column(default=60, server_default="60")
