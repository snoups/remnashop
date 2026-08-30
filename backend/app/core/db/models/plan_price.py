from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.enums import Currency


class PlanPrice(BaseSql):
    __tablename__ = "plan_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_duration_id: Mapped[int] = mapped_column(
        ForeignKey("plan_durations.id", ondelete="CASCADE"), index=True
    )

    currency: Mapped[Currency]
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
