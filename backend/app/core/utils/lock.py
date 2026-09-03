import contextlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from redis.asyncio import Redis
from redis.exceptions import LockNotOwnedError

from app.core.constants import REDIS_KEY_PREFIX


@asynccontextmanager
async def cron_lock(redis: Redis, name: str, *, ttl_seconds: int) -> AsyncGenerator[bool, None]:
    # Guards a cron task against overlapping its own next scheduled run if
    # one execution takes longer than the interval. ttl_seconds auto-releases
    # the lock on a crash, so this is a soft guard, not a hard mutex.
    lock = redis.lock(f"{REDIS_KEY_PREFIX}cron_lock:{name}", timeout=ttl_seconds)
    acquired = await lock.acquire(blocking=False)
    try:
        yield acquired
    finally:
        if acquired:
            with contextlib.suppress(LockNotOwnedError):
                await lock.release()
