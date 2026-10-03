from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import AddOnType


class AddOnEntitlement(BaseSql, TimestampMixin):
    __tablename__ = "addon_entitlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True
    )
    # SET NULL, not CASCADE: the entitlement and its snapshot outlive the
    # catalog entry, as plan_snapshot does
    addon_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("addons.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[AddOnType]  # snapshot, not read through addon_id
    amount: Mapped[int]  # snapshot
    granted_at: Mapped[datetime]
