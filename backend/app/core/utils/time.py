from datetime import datetime, timedelta
from typing import Optional

from remnapy.enums import TrafficLimitStrategy

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


# Rolling reset (N days/weeks/months since subscription creation), not
# calendar-aligned like main's version -- simpler, avoids porting main's
# TIMEZONE-aware midnight/weekday math for a display-only value.
def get_traffic_reset_delta(
    strategy: TrafficLimitStrategy, subscription_created_at: datetime
) -> timedelta:
    if strategy is TrafficLimitStrategy.NO_RESET:
        return timedelta(seconds=0)

    now = datetime_now()
    elapsed = now - subscription_created_at

    if strategy is TrafficLimitStrategy.DAY:
        return timedelta(days=1) - timedelta(
            hours=elapsed.seconds // 3600 % 24, minutes=elapsed.seconds // 60 % 60
        )
    if strategy is TrafficLimitStrategy.WEEK:
        return timedelta(days=7) - timedelta(days=elapsed.days % 7)
    if strategy is TrafficLimitStrategy.MONTH:
        return timedelta(days=30) - timedelta(days=elapsed.days % 30)

    raise ValueError(f"Unhandled TrafficLimitStrategy: {strategy}")
