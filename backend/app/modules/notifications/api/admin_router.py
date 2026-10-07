from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies.admin import require_admin, require_admin_user
from app.api.dependencies.public import get_current_session_id
from app.api.errors import error_responses
from app.core.actor import Actor
from app.modules.notifications.api.schemas import (
    NotificationChannelsResponse,
    NotificationSettingsResponse,
    PushPublicKeyResponse,
    PushSubscriptionListResponse,
    PushSubscriptionResponse,
    SubscribePushRequest,
    TestPushResponse,
    UpdateNotificationChannelsRequest,
    UpdateNotificationSettingsRequest,
)
from app.modules.notifications.dto import (
    NOTIFICATION_GROUPS,
    NotificationChannel,
    NotificationChannelsDto,
    SubscribePushDto,
    UpdateNotificationSettingsDto,
)
from app.modules.notifications.usecases import (
    DeletePushSubscriptionUseCase,
    GenerateVapidKeysUseCase,
    GetNotificationChannelsUseCase,
    GetNotificationSettingsUseCase,
    GetPushPublicKeyUseCase,
    ListPushSubscriptionsUseCase,
    SendTestPushUseCase,
    SubscribePushUseCase,
    UpdateNotificationChannelsUseCase,
    UpdateNotificationSettingsUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/notifications", tags=["notifications"])
settings_router = APIRouter(prefix="/settings/notifications", tags=["notifications"])


def _channels_response(dto: NotificationChannelsDto) -> NotificationChannelsResponse:
    return NotificationChannelsResponse(
        channels=dto.channels,
        available_groups=list(NOTIFICATION_GROUPS),
        available_channels=[c.value for c in NotificationChannel],
        push_configured=dto.push_configured,
        telegram_available=dto.telegram_available,
    )


@router.get("/channels", response_model=NotificationChannelsResponse)
@inject
async def get_notification_channels(
    use_case: FromDishka[GetNotificationChannelsUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> NotificationChannelsResponse:
    return _channels_response(await use_case(actor, None))


@router.put(
    "/channels", response_model=NotificationChannelsResponse, responses=error_responses(400)
)
@inject
async def update_notification_channels(
    body: UpdateNotificationChannelsRequest,
    use_case: FromDishka[UpdateNotificationChannelsUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> NotificationChannelsResponse:
    return _channels_response(await use_case(actor, body.channels))


@router.get("/push/public-key", response_model=PushPublicKeyResponse)
@inject
async def get_push_public_key(
    use_case: FromDishka[GetPushPublicKeyUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> PushPublicKeyResponse:
    return PushPublicKeyResponse(public_key=await use_case(actor, None))


@router.get("/push-subscriptions", response_model=PushSubscriptionListResponse)
@inject
async def list_push_subscriptions(
    use_case: FromDishka[ListPushSubscriptionsUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> PushSubscriptionListResponse:
    items = await use_case(actor, None)
    return PushSubscriptionListResponse(
        items=[PushSubscriptionResponse.model_validate(i, from_attributes=True) for i in items],
        total=len(items),
    )


@router.post(
    "/push-subscriptions",
    response_model=PushSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def subscribe_push(
    body: SubscribePushRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[SubscribePushUseCase],
    actor: UserDto = Depends(require_admin_user),
    session_id: int = Depends(get_current_session_id),
) -> PushSubscriptionResponse:
    subscription, created = await use_case(
        actor,
        SubscribePushDto(
            endpoint=str(body.endpoint),
            p256dh=body.keys.p256dh,
            auth=body.keys.auth,
            session_id=session_id,
            user_agent=(request.headers.get("user-agent") or "")[:512] or None,
        ),
    )
    if not created:
        # the browser was already registered, now under this account
        response.status_code = status.HTTP_200_OK
    return PushSubscriptionResponse.model_validate(subscription, from_attributes=True)


@router.delete(
    "/push-subscriptions/{subscription_id:int}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(404),
)
@inject
async def delete_push_subscription(
    subscription_id: int,
    use_case: FromDishka[DeletePushSubscriptionUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> None:
    await use_case(actor, subscription_id)


@router.post(
    "/push-subscriptions/actions/test",
    response_model=TestPushResponse,
    responses=error_responses(400),
)
@inject
async def send_test_push(
    use_case: FromDishka[SendTestPushUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> TestPushResponse:
    return TestPushResponse(delivered=await use_case(actor, None))


@settings_router.get("", response_model=NotificationSettingsResponse)
@inject
async def get_notification_settings(
    use_case: FromDishka[GetNotificationSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> NotificationSettingsResponse:
    return NotificationSettingsResponse.model_validate(
        await use_case(actor, None), from_attributes=True
    )


@settings_router.patch(
    "", response_model=NotificationSettingsResponse, responses=error_responses(400)
)
@inject
async def update_notification_settings(
    body: UpdateNotificationSettingsRequest,
    use_case: FromDishka[UpdateNotificationSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> NotificationSettingsResponse:
    settings = await use_case(
        actor, UpdateNotificationSettingsDto(vapid_contact=body.vapid_contact)
    )
    return NotificationSettingsResponse.model_validate(settings, from_attributes=True)


@settings_router.post("/actions/generate-vapid-keys", response_model=NotificationSettingsResponse)
@inject
async def generate_vapid_keys(
    use_case: FromDishka[GenerateVapidKeysUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> NotificationSettingsResponse:
    return NotificationSettingsResponse.model_validate(
        await use_case(actor, None), from_attributes=True
    )
