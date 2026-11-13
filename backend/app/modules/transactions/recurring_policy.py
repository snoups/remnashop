from datetime import datetime, timedelta
from typing import Final, Optional

# YooKassa retains idempotency keys for 24h; leave a margin for clock/network delays.
SAFE_REPOST_WINDOW: Final[timedelta] = timedelta(hours=23)
RETRY_OFFSETS_HOURS: Final[tuple[int, ...]] = (1, 3, 6, 12, 24, 36, 48, 72)
# Never automatically retry after the customer revokes the provider-side mandate.
PERMANENT_CANCELLATION_REASONS: Final[frozenset[str]] = frozenset(
    {
        "permission_revoked",
        "payment_method_restricted",
        "card_expired",
        "fraud_suspected",
    }
)
ATTENTION_REASONS: Final[frozenset[str]] = frozenset(
    {
        "payment_status_unknown",
        "pending_timeout",
    }
)


def retry_at(first_failure_at: datetime, retry_count: int) -> Optional[datetime]:
    if retry_count < 0 or retry_count >= len(RETRY_OFFSETS_HOURS):
        return None
    return first_failure_at + timedelta(hours=RETRY_OFFSETS_HOURS[retry_count])
