from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql


class PlanDuration(BaseSql):
    __tablename__ = "plan_durations"
    __table_args__ = (
        CheckConstraint("base_price > 0", name="ck_plan_durations_base_price_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)

    days: Mapped[int]
    order_index: Mapped[int] = mapped_column(index=True)
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
