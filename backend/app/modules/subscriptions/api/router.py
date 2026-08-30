from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, HTTPException, Request, Response, status
from remnapy.controllers.webhooks import WebhookUtility
from remnapy.models.webhook import UserDto as WebhookUserDto

from app.core.config import AppConfig
from app.core.constants import REMNAWAVE_WEBHOOK_PATH
from app.core.enums import SubscriptionStatus
from app.modules.subscriptions.dto import SyncSubscriptionStatusDto
from app.modules.subscriptions.usecases import SyncSubscriptionStatusUseCase

router = APIRouter(tags=["subscriptions"])


@router.post(REMNAWAVE_WEBHOOK_PATH)
@inject
async def receive_remnawave_webhook(
    request: Request,
    use_case: FromDishka[SyncSubscriptionStatusUseCase],
    config: FromDishka[AppConfig],
) -> Response:
    if config.remnawave.webhook_secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Remnawave webhook secret is not configured",
        )

    # No replay protection: remnapy's WebhookUtility signs only the body,
    # not X-Remnawave-Timestamp -- a captured (body, signature) pair stays
    # valid forever. The idempotency guard in SyncSubscriptionStatusUseCase
    # limits the damage (a replayed status equal to the current one is a
    # no-op) but a replayed OLDER status could still overwrite a newer one.
    # Fixing this needs a timestamp-freshness check this SDK doesn't provide.
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

    if not isinstance(payload.data, WebhookUserDto):
        return Response(status_code=status.HTTP_200_OK)

    target_status = (
        SubscriptionStatus.DELETED
        if payload.event == "user.deleted"
        else SubscriptionStatus(payload.data.status)
    )
    await use_case.system(
        SyncSubscriptionStatusDto(
            remnawave_user_id=payload.data.id, status=target_status, source="webhook"
        )
    )
    return Response(status_code=status.HTTP_200_OK)
