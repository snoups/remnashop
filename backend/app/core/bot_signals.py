import json

from redis.asyncio import Redis

from app.core.constants import (
    DIALOG_CONFIG_CHANGED_CHANNEL,
    PAYMENT_OUTCOME_CHANNEL,
    TELEGRAM_RESTART_CHANNEL,
    TRANSLATION_CHANGED_CHANNEL,
)
from app.core.enums import Locale, PaymentOutcome


class RedisBotSignals:
    """BotSignals over Redis pub/sub. Nothing is queued: with no telegram process
    subscribed a signal is dropped (the bot reads fresh state on its next start);
    payment_outcome returns the receiver count so callers can fall back."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def restart(self) -> None:
        await self._redis.publish(TELEGRAM_RESTART_CHANNEL, "restart")

    async def dialogs_changed(self) -> None:
        await self._redis.publish(DIALOG_CONFIG_CHANGED_CHANNEL, "changed")

    async def translation_changed(
        self, locale: Locale, message_id: str, attribute_id: str, value: str
    ) -> None:
        # fluentogram hot-patches message-level keys only; an attribute edit
        # still lands in the DB and reaches the bot on its next restart
        if attribute_id != "":
            return
        payload = json.dumps({"locale": locale.value, "message_id": message_id, "value": value})
        await self._redis.publish(TRANSLATION_CHANGED_CHANNEL, payload)

    async def payment_outcome(
        self, telegram_id: int, order_id: int, outcome: PaymentOutcome
    ) -> int:
        payload = json.dumps(
            {"telegram_id": telegram_id, "order_id": order_id, "outcome": outcome.value}
        )
        return int(await self._redis.publish(PAYMENT_OUTCOME_CHANNEL, payload))
