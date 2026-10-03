from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from remnapy.enums import TrafficLimitStrategy
from sqlalchemy import ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import SubscriptionStatus


class Subscription(BaseSql, TimestampMixin):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index(
            "ux_subscriptions_remnawave_user_id_live",
            "remnawave_user_id",
            unique=True,
            postgresql_where=text(f"status != '{SubscriptionStatus.DELETED.name}'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Remnawave 3.x addresses users by numeric id, not UUID
    # (UserResponseDto.id is `int`). Two live rows must never share a panel
    # user: a partial unique index, not `unique=True`, since a trial->paid
    # conversion or a plan CHANGE marks the row DELETED and inserts a new one
    # with the same remnawave_user_id.
    remnawave_user_id: Mapped[int] = mapped_column(index=True)

    status: Mapped[SubscriptionStatus] = mapped_column(index=True)
    is_trial: Mapped[bool] = mapped_column(default=False, server_default="false")

    traffic_limit: Mapped[int]
    device_limit: Mapped[int]
    traffic_limit_strategy: Mapped[TrafficLimitStrategy]

    tag: Mapped[Optional[str]]
    internal_squads: Mapped[list[UUID]]
    external_squad: Mapped[Optional[UUID]]

    expire_at: Mapped[datetime] = mapped_column(index=True)
    url: Mapped[str]
    # Read/written as one unit (a frozen snapshot of what was purchased),
    # never filtered/joined on a field inside it.
    plan_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)

    device_single_reset_at: Mapped[Optional[datetime]]
    device_all_reset_at: Mapped[Optional[datetime]]
    link_reset_at: Mapped[Optional[datetime]]
