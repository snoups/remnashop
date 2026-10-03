from decimal import Decimal
from typing import Optional

from sqlalchemy import Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import Currency


class PricingSettings(BaseSql, TimestampMixin):
    __tablename__ = "pricing_settings"

    # Single row, always id=1 -- core/db/singleton.py's get_or_create_singleton.
    id: Mapped[int] = mapped_column(primary_key=True)
    anchor_currency: Mapped[Currency] = mapped_column(default=Currency.USD, server_default="USD")
    price_per_day: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    price_per_gb: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
