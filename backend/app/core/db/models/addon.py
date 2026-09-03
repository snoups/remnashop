from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import AddOnType


class AddOn(BaseSql, TimestampMixin):
    __tablename__ = "addons"
    __table_args__ = (CheckConstraint("base_price > 0", name="ck_addons_base_price_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(unique=True, index=True)
    type: Mapped[AddOnType]
    amount: Mapped[int]
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    order_index: Mapped[int] = mapped_column(index=True)
    is_active: Mapped[bool] = mapped_column(default=False, server_default="false")
