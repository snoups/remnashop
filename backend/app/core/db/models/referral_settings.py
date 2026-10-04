from typing import Any

from sqlalchemy import Boolean, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import ReferralAccrualStrategy, ReferralRewardStrategy, ReferralRewardType


class ReferralSettings(BaseSql, TimestampMixin):
    __tablename__ = "referral_settings"

    # single row, id=1 (core/db/singleton.py)
    id: Mapped[int] = mapped_column(primary_key=True)

    enabled: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
    max_level: Mapped[int] = mapped_column(SmallInteger(), default=1, server_default="1")
    accrual_strategy: Mapped[ReferralAccrualStrategy] = mapped_column(
        default=ReferralAccrualStrategy.FIRST_PAYMENT
    )
    reward_type: Mapped[ReferralRewardType] = mapped_column(default=ReferralRewardType.EXTRA_DAYS)
    reward_strategy: Mapped[ReferralRewardStrategy] = mapped_column(
        default=ReferralRewardStrategy.AMOUNT
    )
    # {"1": amount, "2": amount, ...}, a percent under PERCENT; edited as one
    # bundle, never queried per level
    reward_amounts: Mapped[dict[str, Any]] = mapped_column(JSONB(), default=dict)
    days_require_paid_subscription: Mapped[bool] = mapped_column(
        Boolean(), default=True, server_default="true"
    )
