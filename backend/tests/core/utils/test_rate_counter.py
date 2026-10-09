import uuid

from redis.asyncio import Redis

from app.core.utils.rate_counter import hit_counter


async def test_hit_counter_counts_within_window(redis: Redis) -> None:
    key = f"test:rate:{uuid.uuid4()}"
    assert [await hit_counter(redis, key, 30) for _ in range(3)] == [1, 2, 3]
    ttl = await redis.ttl(key)
    assert 0 < ttl <= 30
