from calendar import monthrange
from datetime import datetime, timedelta


def paid_coverage(payments: list[tuple[datetime, int]]) -> list[tuple[datetime, datetime]]:
    # an early renewal extends the current segment, a late one starts a new one
    segments: list[tuple[datetime, datetime]] = []
    for paid_at, days in sorted(payments):
        if segments and paid_at <= segments[-1][1]:
            start, end = segments[-1]
            segments[-1] = (start, max(end, paid_at) + timedelta(days=days))
        else:
            segments.append((paid_at, paid_at + timedelta(days=days)))
    return segments


def is_covered(segments: list[tuple[datetime, datetime]], point: datetime) -> bool:
    return any(start <= point < end for start, end in segments)


def shift_months(moment: datetime, months: int) -> datetime:
    index = moment.month - 1 + months
    year, month = moment.year + index // 12, index % 12 + 1
    return moment.replace(year=year, month=month, day=min(moment.day, monthrange(year, month)[1]))
