from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class BotCommand(BaseSql, TimestampMixin):
    __tablename__ = "bot_commands"

    id: Mapped[int] = mapped_column(primary_key=True)

    command: Mapped[str] = mapped_column(String(32))
    sort_order: Mapped[int] = mapped_column(Integer())
    enabled: Mapped[bool] = mapped_column(Boolean(), default=True, server_default="true")
