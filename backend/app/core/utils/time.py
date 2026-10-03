from datetime import datetime, timedelta
from typing import Optional

from app.core.constants import TIMEZONE


def datetime_now() -> datetime:
    return datetime.now(tz=TIMEZONE)


def truncate_to_ms(value: datetime) -> datetime:
    # Remnawave stores timestamps with millisecond precision
    return value.replace(microsecond=value.microsecond // 1000 * 1000)


def range_start_utc(value: Optional[datetime]) -> Optional[datetime]:
    # a bare "YYYY-MM-DD" parses naive; asyncpg would read that as server
    # local time, so it's pinned to UTC
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=TIMEZONE)


def range_end_utc(value: Optional[datetime]) -> Optional[datetime]:
    # Exclusive upper bound, compared with "<". Same UTC assumption as
    # range_start_utc(), but a bare date is the *whole* day being asked for --
    # so it becomes the next day's midnight.
    if value is None:
        return None
    if value.tzinfo is not None:
        return value
    return value.replace(tzinfo=TIMEZONE) + timedelta(days=1)
