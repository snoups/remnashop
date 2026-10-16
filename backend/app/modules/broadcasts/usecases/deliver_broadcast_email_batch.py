import asyncio
import contextlib
import time
from collections.abc import Callable
from functools import partial
from typing import Final, Optional

from loguru import logger
from redis.asyncio import Redis
from redis.asyncio.lock import Lock
from redis.exceptions import LockNotOwnedError

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.constants import REDIS_KEY_PREFIX
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    BroadcastCategory,
    BroadcastRecipientStatus,
    BroadcastStatus,
    EmailOutcome,
)
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.broadcasts.completion import complete_broadcast, fail_broadcast
from app.modules.broadcasts.dispatch import DeliverBroadcastEmailDispatch
from app.modules.broadcasts.dto import (
    PendingEmailRecipientDto,
    RecipientContextDto,
)
from app.modules.broadcasts.email_assets import load_email_logo, read_email_images
from app.modules.broadcasts.email_html import email_image_ids
from app.modules.broadcasts.email_render import BroadcastEmailRenderer, unsubscribe_links
from app.modules.broadcasts.metrics import BROADCAST_EMAILS
from app.modules.broadcasts.pacing import CLAIM_LEASE, EMAIL_BATCH_WINDOW_S, MAX_ATTEMPTS
from app.modules.broadcasts.render import load_unsubscribe_labels
from app.modules.broadcasts.repository import UNDELIVERABLE_ERROR, BroadcastRepository
from app.modules.broadcasts.validation import promocode_is_usable
from app.modules.email import (
    SMTP_PAUSE_SECONDS,
    EmailDeliveryDto,
    EmailSendError,
    InlineImageDto,
    OutgoingEmailDto,
    SmtpBatchSender,
    load_email_brand,
    smtp_pause_key,
)
from app.modules.promocodes import PromocodeRepository
from app.modules.settings import (
    GetPublicAppearanceImageUseCase,
    SettingsRepository,
    SmtpProfileDto,
)
from app.modules.translations import TranslationRepository
from app.modules.users import UserRepository

_NOT_CONFIGURED: Final[str] = "SMTP is not configured"
_AUTH_FAILED: Final[str] = "SMTP authentication failed"
_IMAGE_MISSING: Final[str] = "Email image is missing"
_USER_GONE: Final[str] = "user gone"


class DeliverBroadcastEmailBatchUseCase(UseCase[int, None]):
    required_permission = None

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        settings_repository: SettingsRepository,
        promocode_repository: PromocodeRepository,
        translation_repository: TranslationRepository,
        user_repository: UserRepository,
        get_public_appearance_image_use_case: GetPublicAppearanceImageUseCase,
        batch_sender: SmtpBatchSender,
        config: AppConfig,
        email_dispatch: DeliverBroadcastEmailDispatch,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        redis: Redis,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._settings_repository = settings_repository
        self._promocode_repository = promocode_repository
        self._translation_repository = translation_repository
        self._user_repository = user_repository
        self._get_public_appearance_image_use_case = get_public_appearance_image_use_case
        self._batch_sender = batch_sender
        self._config = config
        self._email_dispatch = email_dispatch
        self._uow = uow
        self._event_publisher = event_publisher
        self._redis = redis

    async def _execute(self, actor: Actor, data: int) -> None:
        # one email chain per broadcast, independent of the telegram one
        lock = self._redis.lock(
            f"{REDIS_KEY_PREFIX}broadcast_deliver_email:{data}",
            timeout=CLAIM_LEASE.total_seconds(),
        )
        if not await lock.acquire(blocking=False):
            return
        started = time.monotonic()
        try:
            chain = await self._deliver(data, lock)
            if chain:
                # held through the sleep: a tick or retry kick meanwhile is a no-op
                await lock.reacquire()
                # paces batches to bulk_rate_per_minute; the worker slot waits, not the queue
                await asyncio.sleep(max(0.0, EMAIL_BATCH_WINDOW_S - (time.monotonic() - started)))
                chain = await self._still_sending(data)
        finally:
            with contextlib.suppress(LockNotOwnedError):
                await lock.release()
        if chain:
            await self._email_dispatch.kiq(broadcast_id=data)

    async def _deliver(self, data: int, lock: Lock) -> bool:
        # True: more to send (or SMTP paused), kick the next batch after the window
        async with self._uow:
            try:
                broadcast = await self._broadcast_repository.get_by_id_for_update(data)
            except NotFoundError:
                return False
            if broadcast.status is not BroadcastStatus.SENDING or not broadcast.sends_email:
                return False
            settings = await self._settings_repository.get_email_settings()
            profile = settings.profile(bulk=True)
            if not profile.is_configured:
                await fail_broadcast(
                    self._broadcast_repository, self._event_publisher, data, _NOT_CONFIGURED
                )
                return False
            if await self._redis.exists(smtp_pause_key(bulk=profile.is_bulk)):
                # heartbeat: a long pause is not a stall
                await self._broadcast_repository.update_fields(data)
                return True
            pending = await self._broadcast_repository.claim_pending_email(
                data,
                settings.bulk_rate_per_minute,
                CLAIM_LEASE,
                marketing=broadcast.category is BroadcastCategory.MARKETING,
            )
            if not pending:
                # rows still leased by a crashed chain: the stall watchdog re-kicks later
                if not await self._broadcast_repository.has_pending(data):
                    await complete_broadcast(
                        self._broadcast_repository, self._event_publisher, data
                    )
                return False
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
            referenced = set().union(
                *(email_image_ids(c.html) for c in broadcast.email_contents.values())
            )
            image_rows = [
                i
                for i in await self._broadcast_repository.list_email_images(data)
                if i.id in referenced
            ]
            brand = await load_email_brand(self._settings_repository)

        images = await read_email_images(self._config.media_dir, data, image_rows)
        if images is None or images.keys() != referenced:
            async with self._uow:
                await fail_broadcast(
                    self._broadcast_repository, self._event_publisher, data, _IMAGE_MISSING
                )
            return False
        brand, logo = await load_email_logo(self._get_public_appearance_image_use_case, brand)
        cabinet_url = self._config.web_cabinet_url.strip()
        renderer = BroadcastEmailRenderer(
            broadcast,
            promocode_code=code,
            brand=brand,
            unsubscribe=(
                unsubscribe_links(cabinet_url, self._config.crypt_key.get_secret_value())
                if cabinet_url
                else None
            ),
            unsubscribe_labels=labels,
            image_src=lambda i: f"cid:img-{i}",
        )

        compose = partial(self._email, renderer, contexts, images, logo)
        return await self._send_batch(data, lock, profile, list(pending), compose)

    async def _send_batch(
        self,
        broadcast_id: int,
        lock: Lock,
        profile: SmtpProfileDto,
        queue: list[PendingEmailRecipientDto],
        compose: Callable[[PendingEmailRecipientDto], Optional[OutgoingEmailDto]],
    ) -> bool:
        try:
            async with self._batch_sender.open(profile) as batch:
                while queue:
                    # popped only once sent: a dropped connection releases it with the rest
                    email = compose(queue[0])
                    result = None if email is None else await batch.send(email)
                    await self._record(broadcast_id, queue.pop(0), result)
                    await lock.reacquire()
                    if not await self._still_sending(broadcast_id):
                        await self._release(queue)
                        return False
        except EmailSendError as error:
            if error.auth:
                async with self._uow:
                    # fail_pending also fails the rows this batch still holds
                    await fail_broadcast(
                        self._broadcast_repository,
                        self._event_publisher,
                        broadcast_id,
                        _AUTH_FAILED,
                    )
                return False
            if not error.connection:
                raise
            await self._redis.set(smtp_pause_key(bulk=profile.is_bulk), "1", ex=SMTP_PAUSE_SECONDS)
            async with self._uow:
                # heartbeat: a long pause is not a stall
                await self._broadcast_repository.update_fields(broadcast_id)
                await self._broadcast_repository.release_claims([r.id for r in queue])
            logger.warning(f"Broadcast '{broadcast_id}' email paused: {error}")
            return True

        async with self._uow:
            await self._broadcast_repository.refresh_counts(broadcast_id)
        return True

    def _email(
        self,
        renderer: BroadcastEmailRenderer,
        contexts: dict[int, RecipientContextDto],
        images: dict[int, InlineImageDto],
        logo: Optional[InlineImageDto],
        recipient: PendingEmailRecipientDto,
    ) -> Optional[OutgoingEmailDto]:
        # None: the user is gone
        context = contexts.get(recipient.user_id)
        if context is None:
            return None
        rendered = renderer.render(context, datetime_now())
        attached = [images[i] for i in sorted(rendered.image_ids)]
        if logo is not None and "cid:logo" in rendered.html:
            attached.append(logo)
        return OutgoingEmailDto(
            to=recipient.email,
            subject=rendered.subject,
            text=rendered.text,
            html=rendered.html,
            images=attached,
            headers=rendered.headers,
        )

    async def _record(
        self,
        broadcast_id: int,
        recipient: PendingEmailRecipientDto,
        result: Optional[EmailDeliveryDto],
    ) -> None:
        # None: the user is gone
        metric: Optional[str]
        async with self._uow:
            # broadcast row before recipient rows, the order cancel takes them in
            await self._broadcast_repository.update_fields(broadcast_id)
            if result is None:
                await self._broadcast_repository.mark_recipient(
                    recipient.id, BroadcastRecipientStatus.FAILED, error=_USER_GONE
                )
                metric = "failed"
            elif result.outcome is EmailOutcome.SENT:
                await self._broadcast_repository.mark_recipient(
                    recipient.id, BroadcastRecipientStatus.SENT
                )
                metric = "sent"
            elif result.outcome is EmailOutcome.REFUSED:
                await self._broadcast_repository.mark_recipient(
                    recipient.id, BroadcastRecipientStatus.FAILED, error=UNDELIVERABLE_ERROR
                )
                await self._user_repository.set_email_undeliverable(
                    recipient.user_id, datetime_now()
                )
                metric = "undeliverable"
            else:
                await self._broadcast_repository.bump_attempt(
                    recipient.id, MAX_ATTEMPTS, result.error or "retry"
                )
                # counted once, by the bump that gives up on the row
                metric = "failed" if recipient.attempts + 1 >= MAX_ATTEMPTS else None
        if metric is not None:
            BROADCAST_EMAILS.labels(result=metric).inc()

    async def _release(self, rows: list[PendingEmailRecipientDto]) -> None:
        if not rows:
            return
        async with self._uow:
            await self._broadcast_repository.release_claims([r.id for r in rows])

    async def _still_sending(self, broadcast_id: int) -> bool:
        async with self._uow:
            broadcast = await self._broadcast_repository.find_by_id(broadcast_id)
        if broadcast is None:
            return False
        if broadcast.status is BroadcastStatus.SENDING:
            return True
        async with self._uow:
            await self._broadcast_repository.refresh_counts(broadcast_id)
        return False
