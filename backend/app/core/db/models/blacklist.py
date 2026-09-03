from sqlalchemy import ARRAY, BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class Blacklist(BaseSql, TimestampMixin):
    __tablename__ = "blacklist"

    # Single row, always id=1 -- same pattern as BotSettings/BackupSettings.
    id: Mapped[int] = mapped_column(primary_key=True)

    # Manual + CASCADE blocks. Normalised on write (digits-only ids, lowercased
    # emails) -- see modules/blacklist/normalize.py.
    blocked_telegram_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), server_default="{}")
    blocked_emails: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
