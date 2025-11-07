from datetime import datetime, timedelta

from aiogram.methods import SetWebhook
from aiogram.types import WebhookInfo
from loguru import logger

from src.core.security.crypto import get_webhook_hash
from src.core.storage.keys import WebhookLockKey
from src.core.utils.time import datetime_now

from .base import BaseService


class WebhookService(BaseService):
    async def setup(self, allowed_updates: list[str]) -> WebhookInfo:
        safe_webhook_url = self.config.bot.safe_webhook_url(domain=self.config.domain)

        webhook = SetWebhook(
            url=self.config.bot.webhook_url(domain=self.config.domain).get_secret_value(),
            allowed_updates=allowed_updates,
            drop_pending_updates=self.config.bot.drop_pending_updates,
            secret_token=self.config.bot.secret_token.get_secret_value(),
        )

        webhook_data = webhook.model_dump(exclude_unset=True)
        webhook_hash: str = get_webhook_hash(webhook_data)

        if await self._is_set(bot_id=self.bot.id, webhook_hash=webhook_hash):
            logger.info(f"Bot webhook setup skipped, already configured")
            logger.debug(f"Current webhook URL: '{safe_webhook_url}'")
            return await self.bot.get_webhook_info()

        if not await self.bot(webhook):
            raise RuntimeError(f"Failed to set bot webhook on URL '{safe_webhook_url}'")

        await self._clear(bot_id=self.bot.id)
        await self._set(bot_id=self.bot.id, webhook_hash=webhook_hash)

        logger.success(f"Bot webhook set successfully")
        logger.debug(f"Webhook URL: '{safe_webhook_url}'")

        return await self.bot.get_webhook_info()

    async def delete(self) -> None:
        if not self.config.bot.reset_webhook:
            logger.debug(f"Bot webhook reset is disabled")
            return

        if await self.bot.delete_webhook():
            logger.info(f"Bot webhook deleted successfully")
            await self._clear(bot_id=self.bot.id)
        else:
            logger.error(f"Failed to delete bot webhook")

    def has_error(self, webhook_info: WebhookInfo) -> bool:
        if not webhook_info.last_error_message or webhook_info.last_error_date is None:
            return False

        if self._is_new_error(error_time=webhook_info.last_error_date):
            return True
        else:
            return False

    def _is_new_error(self, error_time: datetime, tolerance: int = 5) -> bool:
        current_time = datetime_now()
        time_difference = current_time - error_time
        return time_difference <= timedelta(seconds=tolerance)

    async def _is_set(self, bot_id: int, webhook_hash: str) -> bool:
        key: WebhookLockKey = WebhookLockKey(bot_id=bot_id, webhook_hash=webhook_hash)
        return await self.redis_repository.exists(key)

    async def _set(self, bot_id: int, webhook_hash: str) -> None:
        key: WebhookLockKey = WebhookLockKey(bot_id=bot_id, webhook_hash=webhook_hash)
        await self.redis_repository.set(key, value=None)
        logger.debug(f"Set webhook lock key '{key.pack()}' in Redis")

    async def _clear(self, bot_id: int) -> None:
        key: WebhookLockKey = WebhookLockKey(bot_id=bot_id, webhook_hash="*")
        keys: list[bytes] = await self.redis_repository.client.keys(key.pack())

        if not keys:
            logger.debug(f"No webhook lock keys to clear for bot '{bot_id}'")
            return

        await self.redis_repository.client.delete(*keys)
        logger.debug(f"Cleared '{len(keys)}' webhook lock keys for bot '{bot_id}'")
