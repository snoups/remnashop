from typing import Final

from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.constants import REDIS_KEY_PREFIX, TTL_1H
from app.core.db.uow import UnitOfWork
from app.core.events import BaseEvent
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.settings.dto import BotStatusKind, ReportBotStatusDto
from app.modules.settings.events import (
    BotStartedEvent,
    BotStoppedEvent,
    RequiredChannelCheckFailedEvent,
    TelegramWebhookFailedEvent,
)

_CHANNEL_FAILURE_KEY: Final[str] = f"{REDIS_KEY_PREFIX}channel_check_failed"


class ReportBotStatusUseCase(UseCase[ReportBotStatusDto, None]):
    # system-only: the telegram process reports its own state
    required_permission = None

    def __init__(self, uow: UnitOfWork, event_publisher: EventPublisher, redis: Redis) -> None:
        self._uow = uow
        self._event_publisher = event_publisher
        self._redis = redis

    async def _execute(self, actor: Actor, data: ReportBotStatusDto) -> None:
        event: BaseEvent
        if data.kind is BotStatusKind.CHANNEL_CHECK_FAILED:
            assert data.channel_id is not None
            # every customer message hits the broken check; one report an hour is enough
            key = f"{_CHANNEL_FAILURE_KEY}:{data.channel_id}"
            if not await self._redis.set(key, "1", nx=True, ex=TTL_1H):
                return
            event = RequiredChannelCheckFailedEvent(
                channel_id=data.channel_id, error=data.detail or ""
            )
        elif data.kind is BotStatusKind.WEBHOOK_FAILED:
            event = TelegramWebhookFailedEvent(error=data.detail or "")
        elif data.kind is BotStatusKind.STARTED:
            event = BotStartedEvent(username=data.detail or "")
        else:
            event = BotStoppedEvent()
        async with self._uow:
            await self._event_publisher.publish(event)
