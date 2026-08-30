from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql


class PlanDuration(BaseSql):
    __tablename__ = "plan_durations"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)

    days: Mapped[int]
    order_index: Mapped[int] = mapped_column(index=True)
