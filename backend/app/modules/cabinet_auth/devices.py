import hashlib
from typing import Final, Optional

from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX, TIME_1D
from app.core.utils.http import describe_user_agent, device_bucket
from app.core.utils.time import datetime_now

_KEY_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}cabinet:devices:"
_MAX_DEVICES: Final[int] = 20
_TTL: Final[int] = TIME_1D * 90


class KnownDevices:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def remember(self, user_id: int, ip: str, user_agent: Optional[str]) -> bool:
        key = f"{_KEY_PREFIX}{user_id}"
        device = f"{device_bucket(ip)}|{describe_user_agent(user_agent)}"
        fingerprint = hashlib.sha256(device.encode()).hexdigest()
        had_any = await self._redis.zcard(key) > 0
        added = await self._redis.zadd(key, {fingerprint: datetime_now().timestamp()})
        await self._redis.zremrangebyrank(key, 0, -_MAX_DEVICES - 1)
        await self._redis.expire(key, _TTL)
        return bool(added) and had_any
