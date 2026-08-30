from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import AddOnType


class AddOn(BaseSql, TimestampMixin):
    __tablename__ = "addons"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(unique=True, index=True)
    type: Mapped[AddOnType]
    amount: Mapped[int]

    order_index: Mapped[int] = mapped_column(index=True)
    is_active: Mapped[bool] = mapped_column(default=False, server_default="false")
