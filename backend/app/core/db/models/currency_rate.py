from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import Currency, RoundingMode


class CurrencyRate(BaseSql, TimestampMixin):
    __tablename__ = "currency_rates"

    currency: Mapped[Currency] = mapped_column(primary_key=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    rounding_mode: Mapped[RoundingMode]
    charm_ending: Mapped[Optional[int]]
    min_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    __table_args__ = (
        CheckConstraint("rate > 0", name="ck_currency_rates_rate_positive"),
        CheckConstraint("min_amount >= 0", name="ck_currency_rates_min_amount_nonneg"),
        CheckConstraint(
            "charm_ending IS NULL OR (charm_ending >= 0 AND charm_ending <= 99)",
            name="ck_currency_rates_charm_ending_range",
        ),
    )
