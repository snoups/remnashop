from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX


def user_rate_key(key: str, user_id: int) -> str:
    return f"{REDIS_KEY_PREFIX}ratelimit:{key}:user:{user_id}"


async def hit_counter(redis: Redis, key: str, window_seconds: int) -> int:
    current = int(await redis.incr(key))
    # NX (not "only on current == 1") so a crash between incr() and expire()
    # heals on the next hit instead of leaving the key without a TTL forever
    await redis.expire(key, window_seconds, nx=True)
    return current
