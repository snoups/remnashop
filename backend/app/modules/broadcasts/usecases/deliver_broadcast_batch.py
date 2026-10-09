import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime, timedelta
from functools import partial
from typing import Final, Optional

import httpx
from loguru import logger
from redis.asyncio import Redis
from redis.asyncio.lock import Lock
from redis.exceptions import LockNotOwnedError

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.constants import REDIS_KEY_PREFIX
from app.core.db.uow import UnitOfWork
from app.core.enums import BroadcastCategory, BroadcastRecipientStatus, BroadcastStatus
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dispatch import DeliverBroadcastDispatch, RecallBroadcastDispatch
from app.modules.broadcasts.dto import PendingRecipientDto, RecipientContextDto
from app.modules.broadcasts.events import BroadcastCompletedEvent, BroadcastFailedEvent
from app.modules.broadcasts.render import BroadcastRenderer, load_unsubscribe_labels, outgoing_media
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.telegram_api import (
    OutgoingMedia,
    SendOutcome,
    SendResult,
    TelegramClientFactory,
    send_broadcast_message,
)
from app.modules.broadcasts.validation import promocode_is_usable
from app.modules.promocodes import PromocodeRepository
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationRepository

# every record and flood-wait heartbeat renews the chain lock, so a batch may outlast CLAIM_LEASE
BATCH_SIZE: Final[int] = 100
GROUP_SIZE: Final[int] = 25
GROUP_PAUSE_S: Final[float] = 1.0
MAX_ATTEMPTS: Final[int] = 3
MAX_RETRY_AFTER_S: Final[float] = 60.0
MAX_FLOOD_WAIT_S: Final[float] = 300.0
CLAIM_LEASE: Final[timedelta] = timedelta(minutes=5)
_TOKEN_REJECTED: Final[str] = "Bot token was rejected"
_MEDIA_MISSING: Final[str] = "Media file is missing"
_STOPPED: Final[str] = "stopped"


class DeliverBroadcastBatchUseCase(UseCase[int, None]):
    required_permission = None

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        settings_repository: SettingsRepository,
        promocode_repository: PromocodeRepository,
        translation_repository: TranslationRepository,
        client_factory: TelegramClientFactory,
        config: AppConfig,
        deliver_dispatch: DeliverBroadcastDispatch,
        recall_dispatch: RecallBroadcastDispatch,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        redis: Redis,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._settings_repository = settings_repository
        self._promocode_repository = promocode_repository
        self._translation_repository = translation_repository
        self._client_factory = client_factory
        self._config = config
        self._deliver_dispatch = deliver_dispatch
        self._recall_dispatch = recall_dispatch
        self._uow = uow
        self._event_publisher = event_publisher
        self._redis = redis
        self._lock: Lock
        self._session_lock = asyncio.Lock()

    async def _execute(self, actor: Actor, data: int) -> None:
        # one delivery chain per broadcast; a stall re-kick while it lives is a no-op
        self._lock = self._redis.lock(
            f"{REDIS_KEY_PREFIX}broadcast_deliver:{data}", timeout=CLAIM_LEASE.total_seconds()
        )
        if not await self._lock.acquire(blocking=False):
            return
        try:
            chain = await self._deliver(data)
        finally:
            with contextlib.suppress(LockNotOwnedError):
                await self._lock.release()
        if chain:
            await self._deliver_dispatch.kiq(broadcast_id=data)

    async def _deliver(self, data: int) -> bool:
        # True: more to send, kick the next batch
        async with self._uow:
            try:
                broadcast = await self._broadcast_repository.lock_for_update(data)
            except NotFoundError:
                return False
            if broadcast.status is not BroadcastStatus.SENDING:
                return False
            pending = await self._broadcast_repository.claim_pending(
                data,
                BATCH_SIZE,
                CLAIM_LEASE,
                marketing=broadcast.category is BroadcastCategory.MARKETING,
            )
            if not pending:
                # rows still leased by a crashed chain: the stall watchdog re-kicks later
                if not await self._broadcast_repository.has_pending(data):
                    await self._complete(data)
                return False
            bot = await self._settings_repository.get_bot_settings()
            contexts = await self._broadcast_repository.recipient_contexts(
                [p.user_id for p in pending]
            )
            code = (
                await promocode_is_usable(self._promocode_repository, broadcast.promocode_id)
                if broadcast.promocode_id is not None
                else None
            )
            labels = await load_unsubscribe_labels(
                self._translation_repository,
                sorted({c.language for c in contexts.values()} | {broadcast.default_locale}),
            )
        if bot.token is None:
            await self._fail(data, "Bot token is not set")
            return False

        token = bot.token.get_secret_value()
        renderer = BroadcastRenderer(broadcast, promocode_code=code, unsubscribe_labels=labels)
        media = outgoing_media(self._config.media_dir, broadcast)
        now = datetime_now()
        queue = list(pending)
        async with self._client_factory.open(bot.proxy) as client:
            send = partial(self._send, client, token, renderer, contexts, now, data)
            if media is not None and media.file_id is None:
                uploaded, media = await self._upload_media(data, queue, media, send)
                if not uploaded:
                    return False
            if not await self._send_groups(data, queue, media, send):
                return False

        async with self._uow:
            await self._broadcast_repository.refresh_counts(data)
        return True

    async def _send_groups(
        self,
        broadcast_id: int,
        queue: list[PendingRecipientDto],
        media: Optional[OutgoingMedia],
        send: Callable[[PendingRecipientDto, Optional[OutgoingMedia]], Awaitable[SendResult]],
    ) -> bool:
        for start in range(0, len(queue), GROUP_SIZE):
            group = queue[start : start + GROUP_SIZE]
            # every send finishes and commits before an error leaves the chain
            outcomes = await asyncio.gather(
                *(self._send_and_record(broadcast_id, send, r, media) for r in group),
                return_exceptions=True,
            )
            for outcome in outcomes:
                if isinstance(outcome, BaseException):
                    raise outcome
            if not all(outcomes):
                await self._fail(broadcast_id, _TOKEN_REJECTED)
                return False
            if not await self._still_sending(broadcast_id):
                return False
            await asyncio.sleep(GROUP_PAUSE_S)
        return True

    async def _send_and_record(
        self,
        broadcast_id: int,
        send: Callable[[PendingRecipientDto, Optional[OutgoingMedia]], Awaitable[SendResult]],
        recipient: PendingRecipientDto,
        media: Optional[OutgoingMedia],
    ) -> bool:
        result = await send(recipient, media)
        # sends run concurrently over one session: one transaction at a time
        async with self._session_lock:
            return await self._record(broadcast_id, recipient, result)

    async def _upload_media(
        self,
        broadcast_id: int,
        queue: list[PendingRecipientDto],
        media: OutgoingMedia,
        send: Callable[[PendingRecipientDto, Optional[OutgoingMedia]], Awaitable[SendResult]],
    ) -> tuple[bool, OutgoingMedia]:
        # one at a time until Telegram hands back a reusable file_id; pops what it sends
        while media.file_id is None and queue:
            # the upload can outlast the lease left from the previous record
            if not await self._renew_lock():
                return False, media
            recipient = queue.pop(0)
            try:
                result = await send(recipient, media)
            except FileNotFoundError:
                await self._fail(broadcast_id, _MEDIA_MISSING)
                return False, media
            if not await self._record(broadcast_id, recipient, result):
                await self._fail(broadcast_id, _TOKEN_REJECTED)
                return False, media
            if result.file_id:
                media = replace(media, file_id=result.file_id, path=None)
                async with self._uow:
                    await self._broadcast_repository.update_fields(
                        broadcast_id, media_file_id=result.file_id
                    )
            if not await self._still_sending(broadcast_id):
                return False, media
        return True, media

    async def _send(
        self,
        client: httpx.AsyncClient,
        token: str,
        renderer: BroadcastRenderer,
        contexts: dict[int, RecipientContextDto],
        now: datetime,
        broadcast_id: int,
        recipient: PendingRecipientDto,
        media: Optional[OutgoingMedia],
    ) -> SendResult:
        context = contexts.get(recipient.user_id)
        if context is None:
            return SendResult(outcome=SendOutcome.FAILED, error="user gone")
        message = renderer.render(context, now)
        waited = 0.0
        while True:
            result = await send_broadcast_message(
                client, token, recipient.telegram_id, message.text, message.reply_markup, media
            )
            # a flood wait is not the recipient's fault: no attempt spent until the cap
            if result.outcome is not SendOutcome.RETRY or result.retry_after is None:
                return result
            delay = min(result.retry_after, MAX_RETRY_AFTER_S)
            if waited + delay > MAX_FLOOD_WAIT_S:
                return result
            waited += delay
            await self._heartbeat(broadcast_id)
            await asyncio.sleep(delay)

    async def _renew_lock(self) -> bool:
        try:
            await self._lock.reacquire()
        except LockNotOwnedError:
            # lease lapsed: continue only if nobody took the chain over
            return bool(await self._lock.acquire(blocking=False))
        return True

    async def _heartbeat(self, broadcast_id: int) -> None:
        # stall watchdog reads updated_at; the chain lock must outlive long flood waits
        async with self._session_lock, self._uow:
            await self._broadcast_repository.update_fields(broadcast_id)
        await self._lock.reacquire()

    async def _record(
        self, broadcast_id: int, recipient: PendingRecipientDto, result: SendResult
    ) -> bool:
        # False: token rejected, recipient left pending for the caller to fail the broadcast
        if result.outcome is SendOutcome.UNAUTHORIZED:
            return False
        async with self._uow:
            # broadcast row before recipient rows, the order cancel takes them in
            await self._broadcast_repository.update_fields(broadcast_id)
            if result.outcome is SendOutcome.SENT:
                await self._broadcast_repository.mark_recipient(
                    recipient.id, BroadcastRecipientStatus.SENT, message_id=result.message_id
                )
            elif result.outcome is SendOutcome.BLOCKED:
                await self._broadcast_repository.mark_recipient(
                    recipient.id, BroadcastRecipientStatus.BLOCKED, error=result.error
                )
            elif result.outcome is SendOutcome.FAILED:
                await self._broadcast_repository.mark_recipient(
                    recipient.id, BroadcastRecipientStatus.FAILED, error=result.error
                )
            else:
                await self._broadcast_repository.bump_attempt(
                    recipient.id, MAX_ATTEMPTS, result.error or "retry"
                )
        await self._lock.reacquire()
        return True

    async def _still_sending(self, broadcast_id: int) -> bool:
        async with self._uow:
            broadcast = await self._broadcast_repository.get(broadcast_id)
        if broadcast is None:
            return False
        if broadcast.status is BroadcastStatus.SENDING:
            return True
        async with self._uow:
            await self._broadcast_repository.refresh_counts(broadcast_id)
        # a recall that read its pages before this group landed would miss it
        if broadcast.recall_requested_at is not None:
            await self._recall_dispatch.kiq(broadcast_id=broadcast_id)
        return False

    async def _complete(self, broadcast_id: int) -> None:
        counts = await self._broadcast_repository.refresh_counts(broadcast_id)
        await self._broadcast_repository.update_fields(
            broadcast_id, status=BroadcastStatus.COMPLETED, completed_at=datetime_now()
        )
        await self._event_publisher.publish(
            BroadcastCompletedEvent(
                broadcast_id=broadcast_id,
                sent=counts.sent_count,
                failed=counts.failed_count,
                blocked=counts.blocked_count,
            )
        )
        logger.info(f"Broadcast '{broadcast_id}' completed")

    async def _fail(self, broadcast_id: int, error: str) -> None:
        async with self._uow:
            try:
                broadcast = await self._broadcast_repository.lock_for_update(broadcast_id)
            except NotFoundError:
                return
            if broadcast.status is not BroadcastStatus.SENDING:
                return
            await self._broadcast_repository.update_fields(
                broadcast_id, status=BroadcastStatus.FAILED, completed_at=datetime_now()
            )
            # FAILED, not CANCELED: a retry after fixing the cause resends them
            await self._broadcast_repository.fail_pending(broadcast_id, _STOPPED)
            await self._broadcast_repository.refresh_counts(broadcast_id)
            await self._event_publisher.publish(
                BroadcastFailedEvent(broadcast_id=broadcast_id, error=error)
            )
        logger.warning(f"Broadcast '{broadcast_id}' failed: {error}")
