from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .user import User

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import SubscriptionStatus

from .base import BaseSql
from .timestamp import TimestampMixin


class Subscription(BaseSql, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), nullable=False)
    expire_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    plan: Mapped[dict] = mapped_column(JSON, nullable=False)

    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id"),
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="subscription",
        foreign_keys=[user_telegram_id],
    )
