from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class AddOnGrantIdempotency(BaseSql, TimestampMixin):
    __tablename__ = "addon_grant_idempotency"

    key: Mapped[str] = mapped_column(primary_key=True)
