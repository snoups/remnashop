from typing import Awaitable, cast

from adaptix import Retort
from loguru import logger
from redis.asyncio import Redis

from src.application.common.dao import WaitlistDao
from src.infrastructure.redis.keys import PaymentWaitlistKey


class WaitlistDaoImpl(WaitlistDao):
    def __init__(self, redis: Redis, retort: Retort):
        self.redis = redis
        self.retort = retort

    async def exists(self, telegram_id: int) -> bool:
        raw_key = self.retort.dump(PaymentWaitlistKey())
        is_member = await cast("Awaitable[int]", self.redis.sismember(raw_key, str(telegram_id)))

        if is_member:
            logger.debug(f"User '{telegram_id}' found in waitlist")
        else:
            logger.debug(f"User '{telegram_id}' not found in waitlist")

        return bool(is_member)

    async def add(self, telegram_id: int) -> None:
        raw_key = self.retort.dump(PaymentWaitlistKey())
        await cast("Awaitable[int]", self.redis.sadd(raw_key, str(telegram_id)))
        logger.debug(f"User '{telegram_id}' added to waitlist")

    async def get_members(self) -> list[int]:
        raw_key = self.retort.dump(PaymentWaitlistKey())
        members = await cast("Awaitable[set[bytes]]", self.redis.smembers(raw_key))
        logger.debug(f"Retrieved '{len(members)}' users from waitlist")
        return [int(m) for m in members]

    async def clear(self) -> None:
        raw_key = self.retort.dump(PaymentWaitlistKey())
        await self.redis.delete(raw_key)
        logger.debug("Waitlist cleared")
