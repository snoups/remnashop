from redis.asyncio import Redis


async def hit_counter(redis: Redis, key: str, window_seconds: int) -> int:
    current = int(await redis.incr(key))
    # NX (not "only on current == 1") so a crash between incr() and expire()
    # heals on the next hit instead of leaving the key without a TTL forever
    await redis.expire(key, window_seconds, nx=True)
    return current
