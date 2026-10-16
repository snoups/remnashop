from datetime import timedelta
from typing import Final

# every record and flood-wait heartbeat renews the chain lock, so a batch may outlast CLAIM_LEASE
BATCH_SIZE: Final[int] = 100
GROUP_SIZE: Final[int] = 25
GROUP_PAUSE_S: Final[float] = 1.0
MAX_ATTEMPTS: Final[int] = 3
MAX_RETRY_AFTER_S: Final[float] = 60.0
MAX_FLOOD_WAIT_S: Final[float] = 300.0
CLAIM_LEASE: Final[timedelta] = timedelta(minutes=5)
# an email batch is bulk_rate_per_minute letters, one batch per window
EMAIL_BATCH_WINDOW_S: Final[float] = 60.0
