from datetime import datetime, timezone
from typing import Final

from loguru import logger
from redis.asyncio import Redis
from remnapy.controllers.webhooks import WebhookHeadersDto, WebhookUtility
from remnapy.models.webhook import UserDto as WebhookUserDto

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.constants import REDIS_KEY_PREFIX, TTL_5M, TTL_10M
from app.core.enums import SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError, ValidationError
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.subscriptions.dto import (
    PublishLifecycleEventDto,
    RemnawaveWebhookDto,
    SyncSubscriptionStatusDto,
)
from app.modules.subscriptions.usecases.publish_lifecycle_event import (
    PublishLifecycleEventUseCase,
)
from app.modules.subscriptions.usecases.sync_subscription_status import (
    SyncSubscriptionStatusUseCase,
)

# How far a webhook's timestamp may drift from "now" before it's stale. Read
# from the signed body, not X-Remnawave-Timestamp: the HMAC covers only the
# body, so a replay just sets a fresh header. Inside the window a replay hits
# the dedup key (longer TTL), outside it the timestamp is stale.
_FRESHNESS_WINDOW_S: Final[int] = TTL_5M
_REPLAY_TTL_S: Final[int] = TTL_10M


def _is_stale(timestamp: datetime) -> bool:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return abs((datetime_now() - timestamp).total_seconds()) > _FRESHNESS_WINDOW_S


class HandleRemnawaveWebhookUseCase(UseCase[RemnawaveWebhookDto, None]):
    required_permission = None

    def __init__(
        self,
        sync_subscription_status_use_case: SyncSubscriptionStatusUseCase,
        publish_lifecycle_event_use_case: PublishLifecycleEventUseCase,
        config: AppConfig,
        redis: Redis,
    ) -> None:
        self._sync_subscription_status_use_case = sync_subscription_status_use_case
        self._publish_lifecycle_event_use_case = publish_lifecycle_event_use_case
        self._config = config
        self._redis = redis

    async def _execute(self, actor: Actor, data: RemnawaveWebhookDto) -> None:
        secret = self._config.remnawave.webhook_secret
        assert secret is not None  # the router answers 503 before calling without one

        # The signature header is still required (it keys the replay guard below),
        # but nothing unsigned is trusted: freshness comes from the payload, after
        # the signature has been verified.
        try:
            headers = WebhookHeadersDto.from_headers(data.headers)
            payload = WebhookUtility.parse_webhook(
                data.body.decode("utf-8"), data.headers, secret.get_secret_value()
            )
        except (UnicodeDecodeError, ValueError, KeyError) as error:
            raise ValidationError("Malformed webhook", code=ErrorCode.WEBHOOK_MALFORMED) from error
        if payload is None:
            raise AuthenticationError(
                "Invalid webhook signature", code=ErrorCode.WEBHOOK_SIGNATURE_INVALID
            )
        if _is_stale(payload.timestamp):
            raise AuthenticationError("Webhook timestamp is stale", code=ErrorCode.WEBHOOK_STALE)

        replay_key = f"{REDIS_KEY_PREFIX}remnawave_webhook_seen:{headers.signature}"
        if not await self._redis.set(replay_key, "1", nx=True, ex=_REPLAY_TTL_S):
            # the same signed delivery again: already applied, so acknowledge it
            # instead of making the panel retry
            return

        if not isinstance(payload.data, WebhookUserDto):
            return

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
                )
            )
        except Exception:
            # Release the guard: the panel retries what it couldn't deliver, and a
            # key left behind would answer that retry with "already processed"
            # while nothing was applied.
            await self._redis.delete(replay_key)
            raise

        # a notification must never undo or fail the status sync
        try:
            await self._publish_lifecycle_event_use_case.system(
                PublishLifecycleEventDto(
                    remnawave_user_id=payload.data.id,
                    webhook_event=payload.event,
                    hours=payload.meta.expiration if payload.meta else None,
                )
            )
        except Exception:
            logger.exception(f"Failed to publish lifecycle event '{payload.event}'")
