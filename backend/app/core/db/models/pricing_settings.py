from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import Currency


class PricingSettings(BaseSql, TimestampMixin):
    __tablename__ = "pricing_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    anchor_currency: Mapped[Currency] = mapped_column(default=Currency.USD, server_default="USD")
