from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, SEARCH_MAX_LENGTH
from app.core.enums import SubscriptionStatus
from app.modules.subscriptions.api.schemas import (
    ChangeSubscriptionPlanRequest,
    DeviceItem,
    DeviceListResponse,
    GrantSubscriptionRequest,
    SubscriptionPageResponse,
    SubscriptionResponse,
    UpdateSubscriptionRequest,
    UpdateSubscriptionSquadsRequest,
)
from app.modules.subscriptions.dto import (
    AdminDeleteDeviceDto,
    ChangeSubscriptionPlanDto,
    GrantSubscriptionDto,
    ListSubscriptionsDto,
    SetSubscriptionEnabledDto,
    UpdateSubscriptionDto,
    UpdateSubscriptionSquadsDto,
)
from app.modules.subscriptions.usecases import (
    AdminDeleteAllDevicesUseCase,
    AdminDeleteDeviceUseCase,
    AdminListDevicesUseCase,
    AdminReissueSubscriptionUseCase,
    ChangeSubscriptionPlanUseCase,
    DeleteSubscriptionUseCase,
    GetSubscriptionUseCase,
    GrantSubscriptionUseCase,
    ListSubscriptionsUseCase,
    ResetSubscriptionTrafficUseCase,
    SetSubscriptionEnabledUseCase,
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
    search: Optional[str] = Query(None, max_length=SEARCH_MAX_LENGTH),
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


@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(404, 503),
)
@inject
async def grant_subscription(
    payload: GrantSubscriptionRequest,
    use_case: FromDishka[GrantSubscriptionUseCase],
    actor: Actor = Depends(require_admin),
) -> SubscriptionResponse:
    subscription = await use_case(
        actor,
        GrantSubscriptionDto(
            user_id=payload.user_id, plan_id=payload.plan_id, duration_days=payload.duration_days
        ),
    )
    return SubscriptionResponse.model_validate(subscription, from_attributes=True)


@router.patch(
    "/{subscription_id:int}",
    response_model=SubscriptionResponse,
    responses=error_responses(404, 503),
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
            expire_at=payload.expire_at,
        ),
    )
    return SubscriptionResponse.model_validate(subscription, from_attributes=True)


@router.put(
    "/{subscription_id:int}/squads",
    response_model=SubscriptionResponse,
    responses=error_responses(400, 404, 503),
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
    "/{subscription_id:int}",
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


@router.post(
    "/{subscription_id:int}/actions/change-plan",
    response_model=SubscriptionResponse,
    responses=error_responses(404, 503),
)
@inject
async def change_subscription_plan(
    subscription_id: int,
    payload: ChangeSubscriptionPlanRequest,
    use_case: FromDishka[ChangeSubscriptionPlanUseCase],
    actor: Actor = Depends(require_admin),
) -> SubscriptionResponse:
    subscription = await use_case(
        actor,
        ChangeSubscriptionPlanDto(
            subscription_id=subscription_id,
            plan_id=payload.plan_id,
            duration_days=payload.duration_days,
        ),
    )
    return SubscriptionResponse.model_validate(subscription, from_attributes=True)


@router.post(
    "/{subscription_id:int}/actions/enable",
    response_model=SubscriptionResponse,
    responses=error_responses(404, 503),
)
@inject
async def enable_subscription(
    subscription_id: int,
    use_case: FromDishka[SetSubscriptionEnabledUseCase],
    actor: Actor = Depends(require_admin),
) -> SubscriptionResponse:
    subscription = await use_case(
        actor, SetSubscriptionEnabledDto(subscription_id=subscription_id, enabled=True)
    )
    return SubscriptionResponse.model_validate(subscription, from_attributes=True)


@router.post(
    "/{subscription_id:int}/actions/disable",
    response_model=SubscriptionResponse,
    responses=error_responses(404, 503),
)
@inject
async def disable_subscription(
    subscription_id: int,
    use_case: FromDishka[SetSubscriptionEnabledUseCase],
    actor: Actor = Depends(require_admin),
) -> SubscriptionResponse:
    subscription = await use_case(
        actor, SetSubscriptionEnabledDto(subscription_id=subscription_id, enabled=False)
    )
    return SubscriptionResponse.model_validate(subscription, from_attributes=True)


@router.post(
    "/{subscription_id:int}/actions/reset-traffic",
    response_model=SubscriptionResponse,
    responses=error_responses(404, 503),
)
@inject
async def reset_subscription_traffic(
    subscription_id: int,
    use_case: FromDishka[ResetSubscriptionTrafficUseCase],
    actor: Actor = Depends(require_admin),
) -> SubscriptionResponse:
    return SubscriptionResponse.model_validate(
        await use_case(actor, subscription_id), from_attributes=True
    )


@router.post(
    "/{subscription_id:int}/actions/reissue",
    response_model=SubscriptionResponse,
    responses=error_responses(404, 503),
)
@inject
async def reissue_subscription_link(
    subscription_id: int,
    use_case: FromDishka[AdminReissueSubscriptionUseCase],
    actor: Actor = Depends(require_admin),
) -> SubscriptionResponse:
    return SubscriptionResponse.model_validate(
        await use_case(actor, subscription_id), from_attributes=True
    )


@router.get(
    "/{subscription_id:int}/devices",
    response_model=DeviceListResponse,
    responses=error_responses(404, 503),
)
@inject
async def list_subscription_devices(
    subscription_id: int,
    use_case: FromDishka[AdminListDevicesUseCase],
    actor: Actor = Depends(require_admin),
) -> DeviceListResponse:
    devices = await use_case(actor, subscription_id)
    return DeviceListResponse(
        items=[DeviceItem.model_validate(device, from_attributes=True) for device in devices],
        total=len(devices),
    )


@router.delete(
    "/{subscription_id:int}/devices/{hwid}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(404, 503),
)
@inject
async def delete_subscription_device(
    subscription_id: int,
    hwid: str,
    use_case: FromDishka[AdminDeleteDeviceUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, AdminDeleteDeviceDto(subscription_id=subscription_id, hwid=hwid))


@router.post(
    "/{subscription_id:int}/devices/bulk/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(404, 503),
)
@inject
async def delete_all_subscription_devices(
    subscription_id: int,
    use_case: FromDishka[AdminDeleteAllDevicesUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, subscription_id)
