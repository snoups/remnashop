from calendar import monthrange
from datetime import datetime, timedelta

from app.modules.transactions import PaidTransactionDto


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


def coverage_by_user(
    paid: list[PaidTransactionDto],
) -> tuple[dict[int, datetime], dict[int, list[tuple[datetime, datetime]]]]:
    first_paid: dict[int, datetime] = {}
    payments: dict[int, list[tuple[datetime, int]]] = {}
    for row in paid:
        if row.user_id not in first_paid or row.paid_at < first_paid[row.user_id]:
            first_paid[row.user_id] = row.paid_at
        payments.setdefault(row.user_id, []).append((row.paid_at, row.duration_days))
    return first_paid, {user_id: paid_coverage(items) for user_id, items in payments.items()}
