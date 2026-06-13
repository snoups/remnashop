from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import PromoAudience

from .base import BaseSql
from .plan import Plan
from .timestamp import NOW_FUNC, TimestampMixin


class Promocode(BaseSql, TimestampMixin):
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    discount_percent: Mapped[int]
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"),
        index=True,
    )
    audience: Mapped[PromoAudience]
    max_activations: Mapped[int]
    expires_at: Mapped[datetime]
    is_active: Mapped[bool]

    plan: Mapped["Plan"] = relationship(lazy="selectin")


class PromocodeActivation(BaseSql):
    __tablename__ = "promocode_activations"

    __table_args__ = (
        UniqueConstraint(
            "promocode_id",
            "user_telegram_id",
            name="uq_promo_activation_user",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    promocode_id: Mapped[int] = mapped_column(
        ForeignKey("promocodes.id", ondelete="CASCADE"),
        index=True,
    )
    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id"),
        index=True,
    )
    # Stored without FK — transactions.payment_id has only a unique index, not a constraint
    transaction_payment_id: Mapped[UUID]
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=NOW_FUNC,
    )
