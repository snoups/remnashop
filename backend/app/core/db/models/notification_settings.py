from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.encrypted_string import EncryptedString
from app.core.db.timestamp import TimestampMixin


class NotificationSettings(BaseSql, TimestampMixin):
    __tablename__ = "notification_settings"

    # single row, id=1 (core/db/singleton.py)
    id: Mapped[int] = mapped_column(primary_key=True)

    vapid_public_key: Mapped[Optional[str]] = mapped_column(String(128))
    vapid_private_key: Mapped[Optional[str]] = mapped_column(EncryptedString())
    # mailto: for the VAPID `sub` claim; push services contact it about abuse
    vapid_contact: Mapped[Optional[str]] = mapped_column(String(255))
