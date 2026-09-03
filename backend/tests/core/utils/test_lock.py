import uuid

from redis.asyncio import Redis

from app.core.utils.lock import cron_lock


async def test_cron_lock_acquires_when_free(redis: Redis) -> None:
    async with cron_lock(redis, f"test-{uuid.uuid4()}", ttl_seconds=5) as acquired:
        assert acquired


async def test_cron_lock_rejects_concurrent_holder(redis: Redis) -> None:
    name = f"test-{uuid.uuid4()}"
    async with cron_lock(redis, name, ttl_seconds=5) as outer:
        assert outer
        async with cron_lock(redis, name, ttl_seconds=5) as inner:
            assert not inner


async def test_cron_lock_releases_on_exit(redis: Redis) -> None:
    name = f"test-{uuid.uuid4()}"
    async with cron_lock(redis, name, ttl_seconds=5):
        pass
    async with cron_lock(redis, name, ttl_seconds=5) as acquired:
        assert acquired
