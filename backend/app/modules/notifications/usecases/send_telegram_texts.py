import asyncio
from typing import Final

import httpx
from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.modules.notifications.dto import SendTelegramTextsDto
from app.modules.notifications.sources import BotTokenSource, NotificationRendererFactory
from app.modules.notifications.telegram import (
    TELEGRAM_TIMEOUT_SECONDS,
    TelegramSendResult,
    send_telegram_text,
)
from app.modules.users import UserRepository

# Telegram allows ~30 messages/s per bot; leave headroom for live bot traffic
_SEND_RATE_PER_SECOND: Final[int] = 25
_SEND_PAUSE_S: Final[float] = 1 / _SEND_RATE_PER_SECOND


class SendTelegramTextsUseCase(UseCase[SendTelegramTextsDto, set[int]]):
    required_permission = None

    def __init__(
        self,
        user_repository: UserRepository,
        uow: UnitOfWork,
        token_source: BotTokenSource,
        renderer_factory: NotificationRendererFactory,
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._token_source = token_source
        self._renderer_factory = renderer_factory

    async def _execute(self, actor: Actor, data: SendTelegramTextsDto) -> set[int]:
        token, proxy = await self._token_source.get_bot_token()
        if token is None:
            logger.warning("Bot is not configured, Telegram texts were not sent")
            return set()

        async with self._uow:
            users = await self._user_repository.get_many_by_ids(data.user_ids)
        renderer = await self._renderer_factory.build()

        done = set(data.user_ids) - {user.id for user in users}
        async with httpx.AsyncClient(timeout=TELEGRAM_TIMEOUT_SECONDS, proxy=proxy) as client:
            for user in users:
                if user.telegram_id is None or user.is_blocked or user.deleted_at is not None:
                    done.add(user.id)
                    continue
                text = renderer.text(user.language, data.key)
                if text is None:
                    logger.error(f"Translation '{data.key}' is missing, Telegram texts stopped")
                    break
                result = await send_telegram_text(
                    token, proxy, user.telegram_id, text, client=client
                )
                if result is not TelegramSendResult.FAILED:
                    done.add(user.id)
                await asyncio.sleep(_SEND_PAUSE_S)
        logger.info(f"Telegram texts '{data.key}': {len(done)}/{len(data.user_ids)} done")
        return done
