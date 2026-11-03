from typing import Final

from app.core.constants import REDIS_KEY_PREFIX
from app.modules.backups.dto import STALE_RUN_AFTER

# outlives a run at most by the time it could still count as running
CANCEL_SIGNAL_TTL_S: Final[int] = int(STALE_RUN_AFTER.total_seconds())


def cancel_signal_key(run_id: int) -> str:
    return f"{REDIS_KEY_PREFIX}backup_cancel:{run_id}"
