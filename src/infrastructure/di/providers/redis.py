from collections.abc import AsyncGenerator

from dishka import Provider, Scope, provide
from loguru import logger
from redis.asyncio import ConnectionPool, Redis

from src.core.config import AppConfig


class RedisProvider(Provider):
    scope = Scope.APP

    @provide
    async def get_redis(self, config: AppConfig) -> AsyncGenerator[Redis, None]:
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
