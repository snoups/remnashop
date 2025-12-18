from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .user import User

from datetime import datetime
from uuid import UUID

from remnapy.enums import TrafficLimitStrategy
from sqlalchemy import ARRAY, JSON, BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import SubscriptionStatus
from src.infrastructure.database.models.dto import PlanSnapshotDto

from .base import BaseSql
from .timestamp import TimestampMixin


class Subscription(BaseSql, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_remna_id: Mapped[UUID] = mapped_column(PG_UUID, nullable=False)
    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(
            SubscriptionStatus,
            name="subscription_status",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    is_trial: Mapped[bool] = mapped_column(Boolean, nullable=False)

    traffic_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    device_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    traffic_limit_strategy: Mapped[TrafficLimitStrategy] = mapped_column(
        Enum(
            TrafficLimitStrategy,
            name="traffic_limit_strategy",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    tag: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    internal_squads: Mapped[list[UUID]] = mapped_column(ARRAY(PG_UUID), nullable=False)
    external_squad: Mapped[UUID] = mapped_column(PG_UUID, nullable=True)

    expire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)

    plan: Mapped[PlanSnapshotDto] = mapped_column(JSON, nullable=False)

    user: Mapped["User"] = relationship(
        "User",
        back_populates="subscriptions",
        primaryjoin="Subscription.user_telegram_id==User.telegram_id",
        foreign_keys="Subscription.user_telegram_id",
        lazy="selectin",
    )
