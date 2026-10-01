from datetime import datetime, timezone
from typing import Final

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Request, Response, status
from redis.asyncio import Redis
from remnapy.controllers.webhooks import WebhookHeadersDto, WebhookUtility
from remnapy.models.webhook import UserDto as WebhookUserDto

from app.api.errors import ApiError, error_responses
from app.core.config import AppConfig
from app.core.constants import (
    MAX_WEBHOOK_BODY_BYTES,
    REDIS_KEY_PREFIX,
    REMNAWAVE_WEBHOOK_PATH,
    TTL_5M,
    TTL_10M,
)
from app.core.enums import SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.utils.http import read_bounded_body
from app.core.utils.time import datetime_now
from app.modules.subscriptions.dto import SyncSubscriptionStatusDto
from app.modules.subscriptions.usecases import SyncSubscriptionStatusUseCase

router = APIRouter(tags=["subscriptions"])

# How far a webhook's own timestamp may drift from "now" before it's rejected
# as stale. Read from the signed body, not from X-Remnawave-Timestamp: the
# panel's HMAC covers the body only, so anyone replaying a captured request
# just sets a fresh header. The dedup key's longer TTL closes the gap the
# other way -- inside the freshness window a replay hits the key, outside it
# the body's own timestamp is already stale.
_WEBHOOK_FRESHNESS_WINDOW_S: Final[int] = TTL_5M
_WEBHOOK_REPLAY_TTL_S: Final[int] = TTL_10M


def _is_stale(timestamp: datetime) -> bool:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    drift = abs((datetime_now() - timestamp).total_seconds())
    return drift > _WEBHOOK_FRESHNESS_WINDOW_S


@router.post(REMNAWAVE_WEBHOOK_PATH, responses=error_responses(400, 401, 503))
@inject
async def receive_remnawave_webhook(
    request: Request,
    use_case: FromDishka[SyncSubscriptionStatusUseCase],
    config: FromDishka[AppConfig],
    redis: FromDishka[Redis],
) -> Response:
    if config.remnawave.webhook_secret is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Remnawave webhook secret is not configured",
            code=ErrorCode.WEBHOOK_NOT_CONFIGURED,
        )

    # The signature header is still required (it keys the replay guard below),
    # but nothing unsigned is trusted: freshness comes from the payload, after
    # the signature has been verified.
    try:
        headers = WebhookHeadersDto.from_headers(dict(request.headers))
    except ValueError as error:
        raise ApiError(
            status.HTTP_400_BAD_REQUEST, "Malformed webhook", code=ErrorCode.WEBHOOK_MALFORMED
        ) from error

    body = await read_bounded_body(request, MAX_WEBHOOK_BODY_BYTES)
    try:
        payload = WebhookUtility.parse_webhook(
            body.decode("utf-8"),
            dict(request.headers),
            config.remnawave.webhook_secret.get_secret_value(),
        )
    except (UnicodeDecodeError, ValueError, KeyError) as error:
        raise ApiError(
            status.HTTP_400_BAD_REQUEST, "Malformed webhook", code=ErrorCode.WEBHOOK_MALFORMED
        ) from error
    if payload is None:
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid webhook signature",
            code=ErrorCode.WEBHOOK_SIGNATURE_INVALID,
        )

    if _is_stale(payload.timestamp):
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED, "Webhook timestamp is stale", code=ErrorCode.WEBHOOK_STALE
        )

    replay_key = f"{REDIS_KEY_PREFIX}remnawave_webhook_seen:{headers.signature}"
    if not await redis.set(replay_key, "1", nx=True, ex=_WEBHOOK_REPLAY_TTL_S):
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED,
            "Webhook already processed",
            code=ErrorCode.WEBHOOK_DUPLICATE,
        )

    if not isinstance(payload.data, WebhookUserDto):
        return Response(status_code=status.HTTP_200_OK)

    target_status = (
        SubscriptionStatus.DELETED
        if payload.event == "user.deleted"
        else SubscriptionStatus(payload.data.status)
    )
    is_deletion = target_status is SubscriptionStatus.DELETED
    try:
        await use_case.system(
            SyncSubscriptionStatusDto(
                remnawave_user_id=payload.data.id,
                status=target_status,
                source="webhook",
                expire_at=None if is_deletion else payload.data.expire_at,
            )
        )
    except Exception:
        # Release the guard: the panel retries what it couldn't deliver, and a
        # key left behind would answer that retry with "already processed"
        # while nothing was applied.
        await redis.delete(replay_key)
        raise
    return Response(status_code=status.HTTP_200_OK)
