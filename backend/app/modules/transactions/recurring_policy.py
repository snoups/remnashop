from datetime import timedelta
from typing import Final

# YooKassa retains idempotency keys for 24h. Stop before that boundary so
# an ambiguous request can never become a second debit after a worker restart.
SAFE_REPOST_WINDOW: Final[timedelta] = timedelta(hours=23)
