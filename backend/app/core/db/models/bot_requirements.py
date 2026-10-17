from typing import Optional

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class BotRequirements(BaseSql, TimestampMixin):
    __tablename__ = "bot_requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    rules_required: Mapped[bool] = mapped_column(default=False, server_default="false")
    rules_url: Mapped[Optional[str]] = mapped_column()
    channel_required: Mapped[bool] = mapped_column(default=False, server_default="false")
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    channel_url: Mapped[Optional[str]] = mapped_column()
