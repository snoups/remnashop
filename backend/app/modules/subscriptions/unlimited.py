from calendar import monthrange
from datetime import datetime, timedelta
from typing import Final

from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError

# the panel needs a date; this one reads as "forever" and matches subscriptions
# migrated from the old version
UNLIMITED_EXPIRE_YEAR: Final[int] = 2099


def expiry_after(start: datetime, days: int) -> datetime:
    """The expiry a term of `days` gives from `start`; 0 is an unlimited term."""
    if days < 0:
        raise ValueError(f"A term can't be {days} days")
    if days > 0:
        return start + timedelta(days=days)
    last_day = monthrange(UNLIMITED_EXPIRE_YEAR, start.month)[1]
    return start.replace(year=UNLIMITED_EXPIRE_YEAR, day=min(start.day, last_day))


def is_unlimited_expiry(expire_at: datetime) -> bool:
    return expire_at.year >= UNLIMITED_EXPIRE_YEAR


def assert_not_unlimited_trial(is_trial: bool, unlimited: bool) -> None:
    # a grant, a promocode or an admin's plan change can ask for any term
    if is_trial and unlimited:
        raise ValidationError(
            "A trial plan can't be unlimited", code=ErrorCode.PLAN_TRIAL_UNLIMITED_DURATION
        )
