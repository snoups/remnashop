from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ZERO_AMOUNT
from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import Currency

if TYPE_CHECKING:
    from app.core.db.models.ad_link_attribution import AdLinkAttribution


class AdLink(BaseSql, TimestampMixin):
    __tablename__ = "ad_links"
    __table_args__ = (
        CheckConstraint(
            "revenue_share_percent >= 0 AND revenue_share_percent <= 100",
            name="revenue_share_percent_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=ZERO_AMOUNT, server_default="0")
    cost_currency: Mapped[Currency] = mapped_column(default=Currency.USD, server_default="USD")
    # share of attributed users' payments added to the cost
    revenue_share_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=ZERO_AMOUNT, server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    allow_bot: Mapped[bool] = mapped_column(default=True, server_default="true")
    allow_webcabinet: Mapped[bool] = mapped_column(default=True, server_default="true")
    note: Mapped[Optional[str]] = mapped_column(Text)
    # no cascade into a deleted admin's other data, the attribution is just
    # detached (like Promocode's reward_addon_id/reward_plan_id)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    attributions: Mapped[list["AdLinkAttribution"]] = relationship(
        back_populates="ad_link",
        cascade="all, delete-orphan",
        lazy="noload",
    )
