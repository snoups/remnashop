from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class AddOnGrantIdempotency(BaseSql, TimestampMixin):
    __tablename__ = "addon_grant_idempotency"

    key: Mapped[str] = mapped_column(primary_key=True)
    entitlement_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("addon_entitlements.id", ondelete="SET NULL"), nullable=True, index=True
    )
