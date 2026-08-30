from taskiq_redis import ListQueueBroker

from app.core.config import AppConfig

broker = ListQueueBroker(url=AppConfig.get().redis.dsn)
