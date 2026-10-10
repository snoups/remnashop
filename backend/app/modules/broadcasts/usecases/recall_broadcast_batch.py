import asyncio
from typing import Final

import httpx
from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import BroadcastRecipientStatus
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dispatch import RecallBroadcastDispatch
from app.modules.broadcasts.dto import SentRecipientDto
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.telegram_api import (
    SendOutcome,
    SendResult,
    TelegramClientFactory,
    delete_telegram_message,
)
from app.modules.broadcasts.usecases.deliver_broadcast_batch import (
    BATCH_SIZE,
    GROUP_PAUSE_S,
    GROUP_SIZE,
    MAX_RETRY_AFTER_S,
)
from app.modules.settings import SettingsRepository

# deleted, already gone, too old to delete or bot blocked: nothing left to try
_DONE: Final[frozenset[SendOutcome]] = frozenset(
    {SendOutcome.SENT, SendOutcome.FAILED, SendOutcome.BLOCKED}
)


async def _delete(
    client: httpx.AsyncClient, token: str, chat_id: int, message_id: int
) -> SendResult:
    result = await delete_telegram_message(client, token, chat_id, message_id)
    if result.outcome is SendOutcome.RETRY and result.retry_after is not None:
        await asyncio.sleep(min(result.retry_after, MAX_RETRY_AFTER_S))
        result = await delete_telegram_message(client, token, chat_id, message_id)
    return result


class RecallBroadcastBatchUseCase(UseCase[int, None]):
    required_permission = None

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        settings_repository: SettingsRepository,
        client_factory: TelegramClientFactory,
        recall_dispatch: RecallBroadcastDispatch,
        uow: UnitOfWork,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._settings_repository = settings_repository
        self._client_factory = client_factory
        self._recall_dispatch = recall_dispatch
        self._uow = uow

    async def _recall_rows(
        self, client: httpx.AsyncClient, token: str, rows: list[SentRecipientDto]
    ) -> bool:
        # False: the bot token was rejected, nothing further can be deleted
        for start in range(0, len(rows), GROUP_SIZE):
            group = rows[start : start + GROUP_SIZE]
            results = await asyncio.gather(
                *(_delete(client, token, r.telegram_id, r.telegram_message_id) for r in group)
            )
            async with self._uow:
                for r, result in zip(group, results):
                    if result.outcome in _DONE:
                        await self._broadcast_repository.mark_recipient(
                            r.id, BroadcastRecipientStatus.RECALLED
                        )
                    else:
                        await self._broadcast_repository.mark_recall_failed(
                            r.id, result.error or result.outcome
                        )
            if any(r.outcome is SendOutcome.UNAUTHORIZED for r in results):
                return False
            await asyncio.sleep(GROUP_PAUSE_S)
        return True

    async def _execute(self, actor: Actor, data: int) -> None:
        async with self._uow:
            if await self._broadcast_repository.get(data) is None:
                return
            rows = await self._broadcast_repository.list_recallable(data, BATCH_SIZE)
            channel = await self._broadcast_repository.channel_post(data)
            bot = await self._settings_repository.get_bot_settings()
        if bot.token is None:
            logger.warning(f"Broadcast '{data}' recall skipped: bot token is not set")
            return
        token = bot.token.get_secret_value()
        # a short page means this is the last one; concurrent chains end the same way
        last_page = len(rows) < BATCH_SIZE
        channel_deleted = False
        async with self._client_factory.open(bot.proxy) as client:
            authorized = await self._recall_rows(client, token, rows)
            if last_page and authorized and channel is not None:
                channel_deleted = (await _delete(client, token, *channel)).outcome in _DONE

        async with self._uow:
            if channel_deleted:
                await self._broadcast_repository.update_fields(data, channel_message_id=None)
            await self._broadcast_repository.refresh_counts(data)
            if not last_page and authorized:
                # the repeat window counts from the chain's last batch, not from the click
                await self._broadcast_repository.update_fields(
                    data, recall_requested_at=datetime_now()
                )
                await self._uow.after_commit(lambda: self._recall_dispatch.kiq(broadcast_id=data))
        if not authorized:
            logger.warning(f"Broadcast '{data}' recall stopped: the bot token was rejected")
        elif last_page:
            if channel is not None and not channel_deleted:
                logger.warning(f"Broadcast '{data}' recall could not delete the channel post")
            logger.info(f"Broadcast '{data}' recalled")
