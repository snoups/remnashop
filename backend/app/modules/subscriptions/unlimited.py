from calendar import monthrange
from datetime import datetime, timedelta
from typing import Final

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
