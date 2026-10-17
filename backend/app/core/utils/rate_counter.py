from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX


def user_rate_key(key: str, user_id: int) -> str:
    return f"{REDIS_KEY_PREFIX}ratelimit:{key}:user:{user_id}"


async def hit_counter(redis: Redis, key: str, window_seconds: int) -> int:
    # one MULTI, so the counter never lives without a TTL; NX keeps later
    # hits from pushing the window forward
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        current, _ = await pipe.execute()
    return int(current)
