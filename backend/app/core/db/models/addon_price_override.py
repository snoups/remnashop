from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.enums import Currency


class AddOnPriceOverride(BaseSql):
    __tablename__ = "addon_price_overrides"
    __table_args__ = (UniqueConstraint("addon_id", "currency", name="uq_addon_price_override"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    addon_id: Mapped[int] = mapped_column(ForeignKey("addons.id", ondelete="CASCADE"), index=True)

    currency: Mapped[Currency]
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
