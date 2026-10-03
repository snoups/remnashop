from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import PromocodeAvailability, PromocodeRewardType


class Promocode(BaseSql, TimestampMixin):
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")

    reward_type: Mapped[PromocodeRewardType]
    reward: Mapped[Optional[int]]
    # No ondelete: deleting an AddOn/Plan a promocode still references must fail
    # (RESTRICT, the Postgres default). Unlike AddOnEntitlement.addon_id these
    # aren't snapshots; activation needs them to resolve.
    reward_addon_id: Mapped[Optional[int]] = mapped_column(ForeignKey("addons.id"))
    reward_plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("plans.id"))
    reward_duration_days: Mapped[Optional[int]]

    availability: Mapped[PromocodeAvailability]
    # the ALLOWED-availability allowlist, never queried (like User.permission_grants)
    allowed_user_ids: Mapped[Optional[list[int]]] = mapped_column(JSONB)

    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    max_activations: Mapped[Optional[int]]
    is_reusable: Mapped[bool] = mapped_column(default=False, server_default="false")

    activations: Mapped[list["PromocodeActivation"]] = relationship(
        back_populates="promocode",
        cascade="all, delete-orphan",
        lazy="noload",
    )


class PromocodeActivation(BaseSql):
    __tablename__ = "promocode_activations"

    id: Mapped[int] = mapped_column(primary_key=True)
    promocode_id: Mapped[int] = mapped_column(
        ForeignKey("promocodes.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subscription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL")
    )
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("timezone('UTC', now())")
    )

    promocode: Mapped["Promocode"] = relationship(back_populates="activations")
