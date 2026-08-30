from typing import Optional
from uuid import UUID

from remnapy.enums import TrafficLimitStrategy
from sqlalchemy import ARRAY, BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import PlanAvailability, PlanType


class Plan(BaseSql, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)

    public_code: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)
    description: Mapped[Optional[str]]
    tag: Mapped[Optional[str]]

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
