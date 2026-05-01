from collections.abc import AsyncGenerator
from typing import cast

from dishka import Provider, Scope, provide
from loguru import logger
from redis.asyncio import ConnectionPool, Redis

from src.core.config import AppConfig
from src.infrastructure.redis.memory import InMemoryRedis


class RedisProvider(Provider):
    scope = Scope.APP

    @provide
    async def get_redis(self, config: AppConfig) -> AsyncGenerator[Redis, None]:
        if config.memory_storage:
            logger.info("Using in-memory Redis replacement")
            client = InMemoryRedis()
            yield cast(Redis, client)
            await client.close()
            return

        logger.debug("Connecting to Redis")
        connection_pool = ConnectionPool.from_url(url=config.redis.dsn, decode_responses=True)
        client = Redis(connection_pool=connection_pool)

        try:
            await client.ping()  # type: ignore[misc]
            logger.debug("Successfully connected to Redis")
        except Exception as e:
            logger.exception(f"Failed to connect to Redis: {e}")
            raise

        yield client

        logger.debug("Closing Redis client and disconnecting pool")
        await client.close()
        await connection_pool.disconnect()
