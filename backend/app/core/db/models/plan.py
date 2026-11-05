from datetime import datetime
from typing import Optional
from uuid import UUID

from remnapy.enums import TrafficLimitStrategy
from sqlalchemy import ARRAY, BigInteger, CheckConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import PlanAvailability, PlanBadge, PlanType


class Plan(BaseSql, TimestampMixin):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("discount_percent BETWEEN 0 AND 100", name="discount_percent_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    public_code: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)
    description: Mapped[Optional[str]]
    tag: Mapped[Optional[str]]
    badge: Mapped[Optional[PlanBadge]]

    # shown before the name: a Telegram custom emoji and the glyph it falls back to
    icon_emoji_id: Mapped[Optional[str]]
    icon_emoji_fallback: Mapped[Optional[str]]

    type: Mapped[PlanType]
    availability: Mapped[PlanAvailability]
    traffic_limit_strategy: Mapped[TrafficLimitStrategy]

    traffic_limit: Mapped[int]
    device_limit: Mapped[int]

    allowed_telegram_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), server_default="{}")
    allowed_emails: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    internal_squads: Mapped[list[UUID]]
    external_squad: Mapped[Optional[UUID]]

    order_index: Mapped[int] = mapped_column(index=True)
    is_active: Mapped[bool] = mapped_column(default=False, server_default="false")
    is_trial: Mapped[bool] = mapped_column(default=False, server_default="false")
    allow_bonus_days: Mapped[bool] = mapped_column(default=True, server_default="true")
    allow_promocodes: Mapped[bool] = mapped_column(default=True, server_default="true")

    # applied before the user's own discount; NULL bounds leave that side open
    discount_percent: Mapped[int] = mapped_column(default=0, server_default="0")
    discount_starts_at: Mapped[Optional[datetime]]
    discount_ends_at: Mapped[Optional[datetime]]
