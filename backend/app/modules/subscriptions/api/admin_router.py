from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import SubscriptionStatus
from app.modules.subscriptions.api.schemas import (
    SubscriptionPageResponse,
    SubscriptionResponse,
    UpdateSubscriptionRequest,
    UpdateSubscriptionSquadsRequest,
)
from app.modules.subscriptions.dto import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    ListSubscriptionsDto,
    UpdateSubscriptionDto,
    UpdateSubscriptionSquadsDto,
)
from app.modules.subscriptions.usecases import (
    DeleteSubscriptionUseCase,
    GetSubscriptionUseCase,
    ListSubscriptionsUseCase,
    UpdateSubscriptionSquadsUseCase,
    UpdateSubscriptionUseCase,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("", response_model=SubscriptionPageResponse)
@inject
async def list_subscriptions(
    use_case: FromDishka[ListSubscriptionsUseCase],
    actor: Actor = Depends(require_admin),
    status_filter: Optional[SubscriptionStatus] = Query(None, alias="status"),
    search: Optional[str] = None,
    user_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> SubscriptionPageResponse:
    subscriptions, total = await use_case(
        actor,
        ListSubscriptionsDto(
            status=status_filter, search=search, user_id=user_id, page=page, page_size=page_size
        ),
    )
    return SubscriptionPageResponse(
        items=[
            SubscriptionResponse.model_validate(subscription, from_attributes=True)
            for subscription in subscriptions
        ],
        total=total,
    )


@router.patch(
    "/{subscription_id}", response_model=SubscriptionResponse, responses=error_responses(404, 503)
)
@inject
async def update_subscription(
    subscription_id: int,
    payload: UpdateSubscriptionRequest,
    use_case: FromDishka[UpdateSubscriptionUseCase],
    actor: Actor = Depends(require_admin),
) -> SubscriptionResponse:
    subscription = await use_case(
        actor,
        UpdateSubscriptionDto(
            subscription_id=subscription_id,
            tag=payload.tag,
            traffic_limit=payload.traffic_limit,
            device_limit=payload.device_limit,
            traffic_limit_strategy=payload.traffic_limit_strategy,
        ),
    )
    return SubscriptionResponse.model_validate(subscription, from_attributes=True)


@router.put(
    "/{subscription_id}/squads",
    response_model=SubscriptionResponse,
    responses=error_responses(404, 503),
)
@inject
async def update_subscription_squads(
    subscription_id: int,
    payload: UpdateSubscriptionSquadsRequest,
    use_case: FromDishka[UpdateSubscriptionSquadsUseCase],
    actor: Actor = Depends(require_admin),
) -> SubscriptionResponse:
    subscription = await use_case(
        actor,
        UpdateSubscriptionSquadsDto(
            subscription_id=subscription_id,
            internal_squads=payload.internal_squads,
            external_squad=payload.external_squad,
        ),
    )
    return SubscriptionResponse.model_validate(subscription, from_attributes=True)


@router.delete(
    "/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(404, 503),
)
@inject
async def delete_subscription(
    subscription_id: int,
    use_case: FromDishka[DeleteSubscriptionUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, subscription_id)


@router.get(
    "/{subscription_id:int}", response_model=SubscriptionResponse, responses=error_responses(404)
)
@inject
async def get_subscription(
    subscription_id: int,
    use_case: FromDishka[GetSubscriptionUseCase],
    actor: Actor = Depends(require_admin),
) -> SubscriptionResponse:
    return SubscriptionResponse.model_validate(
        await use_case(actor, subscription_id), from_attributes=True
    )
