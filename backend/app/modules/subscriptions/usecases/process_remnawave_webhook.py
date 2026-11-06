import contextlib
import json
from datetime import datetime, timedelta, timezone
from typing import Final

from loguru import logger
from redis.asyncio import Redis
from redis.exceptions import LockNotOwnedError
from remnapy.models.webhook import UserDto as WebhookUserDto
from remnapy.models.webhook import WebhookPayloadDto

from app.core.actor import Actor
from app.core.constants import REDIS_KEY_PREFIX, TIME_1M, TTL_10M
from app.core.enums import SubscriptionStatus
from app.core.exceptions import RetryableTaskError
from app.core.panel_writes import WRITE_MARK_TTL_S, written_after
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.subscriptions.dto import (
    ProcessRemnawaveWebhookDto,
    PublishPanelEventDto,
    SyncSubscriptionStatusDto,
)
from app.modules.subscriptions.panel_config import panel_config
from app.modules.subscriptions.usecases.publish_panel_event import PublishPanelEventUseCase
from app.modules.subscriptions.usecases.sync_subscription_status import (
    SyncSubscriptionStatusUseCase,
)

# panel user -> timestamp of the newest event applied to them
_APPLIED_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}remnawave_webhook_applied:"
# outlives the task's retries (~45s and ~105s after the first attempt)
_APPLIED_TTL_S: Final[int] = TTL_10M
# one panel user's events are checked and applied one at a time
_LOCK_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}remnawave_webhook_lock:"
_LOCK_TTL_S: Final[int] = TIME_1M
_LOCK_WAIT_S: Final[float] = 10


def _utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


class ProcessRemnawaveWebhookUseCase(UseCase[ProcessRemnawaveWebhookDto, None]):
    # system-only: run from the worker for a webhook the api has verified and queued
    required_permission = None

    def __init__(
        self,
        sync_subscription_status_use_case: SyncSubscriptionStatusUseCase,
        publish_panel_event_use_case: PublishPanelEventUseCase,
        redis: Redis,
    ) -> None:
        self._sync_subscription_status_use_case = sync_subscription_status_use_case
        self._publish_panel_event_use_case = publish_panel_event_use_case
        self._redis = redis

    async def _execute(self, actor: Actor, data: ProcessRemnawaveWebhookDto) -> None:
        payload = WebhookPayloadDto.from_dict(json.loads(data.body))
        if isinstance(payload.data, WebhookUserDto):
            if not await self._apply(payload):
                return

        # a notification must never undo or fail the status sync
        try:
            await self._publish_panel_event_use_case.system(PublishPanelEventDto(payload=payload))
        except Exception:
            logger.exception(f"Failed to publish panel event '{payload.event}'")

    async def _apply(self, payload: WebhookPayloadDto) -> bool:
        """Syncs the subscription from a user event; False when the event is outdated."""
        assert isinstance(payload.data, WebhookUserDto)
        user_id = payload.data.id
        moment = _utc(payload.timestamp)
        # older than the shop's write marks: a write made after it can't be ruled out
        if datetime_now() - moment > timedelta(seconds=WRITE_MARK_TTL_S):
            logger.warning(
                f"Skipped the sync of '{payload.event}' for panel user {user_id}: "
                f"the event is from {moment.isoformat()}"
            )
            return True
        lock = self._redis.lock(f"{_LOCK_PREFIX}{user_id}", timeout=_LOCK_TTL_S)
        if not await lock.acquire(blocking_timeout=_LOCK_WAIT_S):
            raise RetryableTaskError(f"Panel user {user_id} is being synced by another event")
        try:
            # built before our own later write to this user and delivered after
            # it: its state is outdated, and our write's echo carries the current one
            if await written_after(self._redis, user_id, moment):
                logger.info(
                    f"Skipped '{payload.event}' for panel user {user_id}: "
                    "the shop changed the user after the event was built"
                )
                return False
            # a retried or parallel event must not undo a newer one applied before it
            if await self._applied_after(user_id, moment):
                logger.info(
                    f"Skipped '{payload.event}' for panel user {user_id}: "
                    "a newer event was applied already"
                )
                return False
            await self._sync_status(payload)
            await self._redis.set(
                f"{_APPLIED_PREFIX}{user_id}", moment.isoformat(), ex=_APPLIED_TTL_S
            )
            return True
        finally:
            with contextlib.suppress(LockNotOwnedError):
                await lock.release()

    async def _applied_after(self, user_id: int, moment: datetime) -> bool:
        raw = await self._redis.get(f"{_APPLIED_PREFIX}{user_id}")
        return raw is not None and datetime.fromisoformat(raw) > moment

    async def _sync_status(self, payload: WebhookPayloadDto) -> None:
        assert isinstance(payload.data, WebhookUserDto)
        target_status = (
            SubscriptionStatus.DELETED
            if payload.event == "user.deleted"
            else SubscriptionStatus(payload.data.status)
        )
        is_deletion = target_status is SubscriptionStatus.DELETED
        try:
            await self._sync_subscription_status_use_case.system(
                SyncSubscriptionStatusDto(
                    remnawave_user_id=payload.data.id,
                    status=target_status,
                    source="webhook",
                    expire_at=None if is_deletion else payload.data.expire_at,
                    first_connected_at=payload.data.first_connected_at,
                    # limits, squads, tag and link changed in the panel come over too
                    config=None if is_deletion else panel_config(payload.data),
                )
            )
        except Exception as error:
            # the sync's transaction rolled back, so nothing is applied yet
            raise RetryableTaskError(f"Panel user {payload.data.id} sync failed") from error
