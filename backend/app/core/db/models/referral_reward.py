from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import ReferralRewardType


class ReferralReward(BaseSql, TimestampMixin):
    __tablename__ = "referral_rewards"
    __table_args__ = (
        # one reward per paid order per chain hop -- a subscription's renewals
        # are separate payments
        UniqueConstraint("payment_key", "referral_id", name="uq_referral_rewards_payment_referral"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # All SET NULL, not CASCADE: this is the money ledger -- deleting a
    # referrer, the referral edge, or the triggering subscription later must
    # not erase the historical record that an amount was already paid out.
    referral_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("referrals.id", ondelete="SET NULL")
    )
    referrer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    subscription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL")
    )
    # Transaction.idempotency_key of the payment that earned this reward
    payment_key: Mapped[str] = mapped_column(String(36))
    type: Mapped[ReferralRewardType]
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 0))
