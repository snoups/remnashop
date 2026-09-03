from typing import Any

from sqlalchemy import Boolean, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import ReferralAccrualStrategy, ReferralRewardType


class ReferralSettings(BaseSql, TimestampMixin):
    __tablename__ = "referral_settings"

    # Single row, always id=1 -- same get-or-create pattern as BotSettings.
    id: Mapped[int] = mapped_column(primary_key=True)

    enabled: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
    max_level: Mapped[int] = mapped_column(SmallInteger(), default=1, server_default="1")
    accrual_strategy: Mapped[ReferralAccrualStrategy] = mapped_column(
        default=ReferralAccrualStrategy.FIRST_PAYMENT
    )
    reward_type: Mapped[ReferralRewardType] = mapped_column(default=ReferralRewardType.EXTRA_DAYS)
    # {"1": amount, "2": amount, ...} -- an always-atomic settings bundle
    # edited together as one unit, not independently queryable per level.
    reward_amounts: Mapped[dict[str, Any]] = mapped_column(JSONB(), default=dict)
