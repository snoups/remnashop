from typing import Any

from taskiq import AsyncResultBackend
from taskiq_redis import RedisAsyncResultBackend, RedisStreamBroker

from src.core.config import AppConfig


def create_broker(config: AppConfig) -> RedisStreamBroker:
    result_backend: AsyncResultBackend[Any] = RedisAsyncResultBackend(redis_url=config.redis.dsn)
    broker = RedisStreamBroker(url=config.redis.dsn).with_result_backend(result_backend)
    return broker


broker = create_broker(config=AppConfig.get())
