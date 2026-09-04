from datetime import datetime, timezone
from typing import Final, Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, HTTPException, Request, Response, status
from redis.asyncio import Redis
from remnapy.controllers.webhooks import WebhookHeadersDto, WebhookUtility
from remnapy.models.webhook import UserDto as WebhookUserDto

from app.core.config import AppConfig
from app.core.constants import REDIS_KEY_PREFIX, REMNAWAVE_WEBHOOK_PATH, TTL_5M, TTL_10M
from app.core.enums import SubscriptionStatus
from app.modules.subscriptions.dto import SyncSubscriptionStatusDto
from app.modules.subscriptions.usecases import SyncSubscriptionStatusUseCase

router = APIRouter(tags=["subscriptions"])

# How far a webhook's own X-Remnawave-Timestamp may drift from "now" before
# it's rejected as stale -- narrows the window a captured (body, signature)
# pair (the HMAC covers only the body, not this header -- see below) stays
# replayable. TTL_10M for the dedup key gives a comfortable margin over the
# freshness window itself.
_WEBHOOK_FRESHNESS_WINDOW_S: Final[int] = TTL_5M
_WEBHOOK_REPLAY_TTL_S: Final[int] = TTL_10M


def _parse_webhook_timestamp(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    try:
        value = float(raw)
    except ValueError:
        value = None
    if value is not None:
        if value > 10**12:  # milliseconds since epoch, not seconds
            value /= 1000
        return datetime.fromtimestamp(value, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


@router.post(REMNAWAVE_WEBHOOK_PATH)
@inject
async def receive_remnawave_webhook(
    request: Request,
    use_case: FromDishka[SyncSubscriptionStatusUseCase],
    config: FromDishka[AppConfig],
    redis: FromDishka[Redis],
) -> Response:
    if config.remnawave.webhook_secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Remnawave webhook secret is not configured",
        )

    # remnapy's WebhookUtility signs only the body, not X-Remnawave-Timestamp,
    # so a captured (body, signature) pair is valid forever from the SDK's own
    # perspective. Compensated for here with two independent checks before the
    # signature is even verified: the header's own freshness (rejects an old
    # replay outright) and a Redis-backed single-use guard keyed on the
    # signature (rejects a replay of a still-fresh, already-processed webhook).
    try:
        headers = WebhookHeadersDto.from_headers(dict(request.headers))
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed webhook"
        ) from error

    webhook_timestamp = _parse_webhook_timestamp(headers.timestamp)
    if webhook_timestamp is None or (
        abs((datetime.now(timezone.utc) - webhook_timestamp).total_seconds())
        > _WEBHOOK_FRESHNESS_WINDOW_S
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook timestamp is stale"
        )

    body = await request.body()
    try:
        payload = WebhookUtility.parse_webhook(
            body.decode("utf-8"),
            dict(request.headers),
            config.remnawave.webhook_secret.get_secret_value(),
        )
    except (UnicodeDecodeError, ValueError, KeyError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed webhook"
        ) from error
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature"
        )

    replay_key = f"{REDIS_KEY_PREFIX}remnawave_webhook_seen:{headers.signature}"
    if not await redis.set(replay_key, "1", nx=True, ex=_WEBHOOK_REPLAY_TTL_S):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook already processed"
        )

    if not isinstance(payload.data, WebhookUserDto):
        return Response(status_code=status.HTTP_200_OK)

    target_status = (
        SubscriptionStatus.DELETED
        if payload.event == "user.deleted"
        else SubscriptionStatus(payload.data.status)
    )
    is_deletion = target_status is SubscriptionStatus.DELETED
    await use_case.system(
        SyncSubscriptionStatusDto(
            remnawave_user_id=payload.data.id,
            status=target_status,
            source="webhook",
            expire_at=None if is_deletion else payload.data.expire_at,
        )
    )
    return Response(status_code=status.HTTP_200_OK)
