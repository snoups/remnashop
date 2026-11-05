from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class Referral(BaseSql, TimestampMixin):
    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint("referred_id", name="uq_referrals_referred_id"),
        CheckConstraint("level BETWEEN 1 AND 3", name="level_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # SET NULL, not CASCADE: deleting a referrer loses only the "who invited
    # them" link, not the referred user
    referrer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    referred_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    level: Mapped[int] = mapped_column(SmallInteger())
