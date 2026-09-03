from datetime import datetime, timedelta
from typing import Optional

from app.core.constants import TIMEZONE


def datetime_now() -> datetime:
    return datetime.now(tz=TIMEZONE)


def range_start_utc(value: Optional[datetime]) -> Optional[datetime]:
    # A bare "YYYY-MM-DD" (e.g. from an <input type="date">) parses into a
    # naive datetime -- treat it as UTC rather than the server's local
    # timezone, which asyncpg would otherwise assume for a naive value.
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=TIMEZONE)


def range_end_utc(value: Optional[datetime]) -> Optional[datetime]:
    # Same UTC assumption as range_start_utc(), but a bare date is also the
    # *whole* day being asked for -- push it to the day's last instant so an
    # inclusive "<=" comparison doesn't exclude every event after midnight.
    if value is None:
        return None
    if value.tzinfo is not None:
        return value
    start_of_day = value.replace(tzinfo=TIMEZONE)
    return start_of_day + timedelta(days=1) - timedelta(microseconds=1)
