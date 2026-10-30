from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies.public import get_current_session_id, get_current_user
from app.api.dependencies.rate_limit import rate_limit
from app.api.errors import error_responses
from app.core.constants import TIME_1M
from app.modules.notifications.api.schemas import (
    PushPublicKeyResponse,
    PushSubscriptionListResponse,
    PushSubscriptionResponse,
    SubscribePushRequest,
)
from app.modules.notifications.dto import SubscribePushDto
from app.modules.notifications.usecases import (
    DeleteCustomerPushSubscriptionUseCase,
    GetCustomerPushPublicKeyUseCase,
    ListCustomerPushSubscriptionsUseCase,
    SubscribeCustomerPushUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/notifications/me", tags=["notifications"])


@router.get("/push/public-key", response_model=PushPublicKeyResponse)
@inject
async def get_my_push_public_key(
    use_case: FromDishka[GetCustomerPushPublicKeyUseCase],
    actor: UserDto = Depends(get_current_user),
) -> PushPublicKeyResponse:
    return PushPublicKeyResponse(public_key=await use_case(actor))


@router.get("/push-subscriptions", response_model=PushSubscriptionListResponse)
@inject
async def list_my_push_subscriptions(
    use_case: FromDishka[ListCustomerPushSubscriptionsUseCase],
    actor: UserDto = Depends(get_current_user),
) -> PushSubscriptionListResponse:
    items = await use_case(actor)
    return PushSubscriptionListResponse(
        items=[PushSubscriptionResponse.model_validate(i, from_attributes=True) for i in items],
        total=len(items),
    )


@router.post(
    "/push-subscriptions",
    response_model=PushSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400),
    dependencies=[
        Depends(rate_limit(key="cabinet_push_subscribe", limit=10, window_seconds=TIME_1M))
    ],
)
@inject
async def subscribe_my_push(
    body: SubscribePushRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[SubscribeCustomerPushUseCase],
    actor: UserDto = Depends(get_current_user),
    session_id: int = Depends(get_current_session_id),
) -> PushSubscriptionResponse:
    subscribed = await use_case(
        actor,
        SubscribePushDto(
            endpoint=str(body.endpoint),
            p256dh=body.keys.p256dh,
            auth=body.keys.auth,
            session_id=session_id,
            user_agent=request.headers.get("user-agent"),
        ),
    )
    if not subscribed.created:
        response.status_code = status.HTTP_200_OK
    return PushSubscriptionResponse.model_validate(subscribed.subscription, from_attributes=True)


@router.delete(
    "/push-subscriptions/{subscription_id:int}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(404),
)
@inject
async def delete_my_push_subscription(
    subscription_id: int,
    use_case: FromDishka[DeleteCustomerPushSubscriptionUseCase],
    actor: UserDto = Depends(get_current_user),
) -> None:
    await use_case(actor, subscription_id)
