from collections.abc import AsyncGenerator

from dishka import Provider, Scope, provide
from loguru import logger
from redis.asyncio import ConnectionPool, Redis

from src.core.config import AppConfig
from src.infrastructure.redis import RedisRepository


class RedisProvider(Provider):
    scope = Scope.APP

    @provide
    async def get_redis_client(self, config: AppConfig) -> AsyncGenerator[Redis, None]:
        logger.debug("Connecting to Redis")
        connection_pool = ConnectionPool.from_url(url=config.redis.dsn)
        client = Redis(connection_pool=connection_pool)

        try:
            await client.ping()
            logger.debug("Successfully connected to Redis")
        except Exception as exception:
            logger.error(f"Failed to connect to Redis: {exception}")
            raise

        yield client

        logger.debug("Closing Redis client and disconnecting pool")
        await client.close()
        await connection_pool.disconnect()

    redis_repository = provide(source=RedisRepository)
