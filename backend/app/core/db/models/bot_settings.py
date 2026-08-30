from typing import Optional

from sqlalchemy import Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.encrypted_string import EncryptedString
from app.core.db.timestamp import TimestampMixin


class BotSettings(BaseSql, TimestampMixin):
    __tablename__ = "bot_settings"

    # Single row, always id=1 -- see modules/settings/repository.py.
    id: Mapped[int] = mapped_column(primary_key=True)

    # Fernet-encrypted (APP_CRYPT_KEY) transparently by EncryptedString.
    token: Mapped[Optional[str]] = mapped_column(EncryptedString())
    secret_token: Mapped[Optional[str]] = mapped_column(EncryptedString())

    drop_pending_updates: Mapped[bool] = mapped_column(
        Boolean(), default=False, server_default="false"
    )
    banners_enabled: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
