from typing import List, Optional

from adaptix import Retort
from loguru import logger
from redis.asyncio import Redis

from src.application.common.dao import WebhookDao
from src.infrastructure.common import json
from src.infrastructure.redis.keys import WebhookLockKey


class WebhookDaoImpl(WebhookDao):
    def __init__(self, redis: Redis, retort: Retort):
        self.redis = redis
        self.retort = retort

    async def is_hash_exists(self, bot_id: int, webhook_hash: str) -> bool:
        key = WebhookLockKey(bot_id=bot_id, webhook_hash=webhook_hash)
        raw_key = self.retort.dump(key)
        exists = await self.redis.exists(raw_key)

        if exists:
            logger.debug(f"Webhook hash '{webhook_hash}' found for bot '{bot_id}'")
        else:
            logger.debug(f"Webhook hash '{webhook_hash}' not found for bot '{bot_id}'")

        return bool(exists)

    async def save_hash(self, bot_id: int, webhook_hash: str) -> None:
        key = WebhookLockKey(bot_id=bot_id, webhook_hash=webhook_hash)
        raw_key = self.retort.dump(key)
        await self.redis.set(name=raw_key, value=json.encode(None), ex=86400 * 30)
        logger.debug(f"Webhook lock hash '{webhook_hash}' saved for bot '{bot_id}'")

    async def clear_all_hashes(self, bot_id: int) -> None:
        pattern_key = WebhookLockKey(bot_id=bot_id, webhook_hash="*")
        raw_pattern_key = self.retort.dump(pattern_key)
        keys: List[str] = [k async for k in self.redis.scan_iter(match=raw_pattern_key)]

        if not keys:
            logger.debug(f"No webhook lock keys found to clear for bot '{bot_id}'")
            return

        await self.redis.delete(*keys)
        logger.debug(f"Cleared '{len(keys)}' old webhook lock keys for bot '{bot_id}'")

    async def get_current_hash(self, bot_id: int) -> Optional[str]:
        pattern_key = WebhookLockKey(bot_id=bot_id, webhook_hash="*")
        raw_pattern_key = self.retort.dump(pattern_key)
        keys: list[str] = [k async for k in self.redis.scan_iter(match=raw_pattern_key)]

        if not keys:
            logger.debug(f"No webhook hash found for bot '{bot_id}'")
            return None

        current_hash: str = keys[0].split(":")[-1]

        logger.debug(f"Retrieved current hash '{current_hash}' for bot '{bot_id}'")
        return current_hash
