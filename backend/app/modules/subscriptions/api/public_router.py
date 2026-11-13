from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.public import get_current_user
from app.api.errors import error_responses
from app.core.config import AppConfig
from app.modules.subscriptions.api.schemas import (
    ActivateTrialRequest,
    DeviceListResponse,
    DeviceResponse,
    OwnSubscriptionListResponse,
    OwnSubscriptionResponse,
    PublicPlanListResponse,
    PublicPlanPriceResponse,
    PublicPlanResponse,
    TrialResponse,
)
from app.modules.subscriptions.dto import (
    ActivateTrialDto,
    DeleteDeviceDto,
    ListActivePlansDto,
    SubscriptionRefDto,
)
from app.modules.subscriptions.usecases import (
    ActivateTrialSubscriptionUseCase,
    DeleteAllDevicesUseCase,
    DeleteDeviceUseCase,
    GetAvailableTrialUseCase,
    ListActivePlansUseCase,
    ListDevicesUseCase,
    ListOwnSubscriptionsUsageUseCase,
    ReissueSubscriptionUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/catalog", response_model=PublicPlanListResponse)
@inject
async def list_active_plans(
    use_case: FromDishka[ListActivePlansUseCase],
    actor: UserDto = Depends(get_current_user),
    plan_code: Optional[str] = Query(None, max_length=64),
    renew_subscription_id: Optional[int] = Query(None),
) -> PublicPlanListResponse:
    catalog = await use_case(
        actor,
        ListActivePlansDto(plan_code=plan_code, renew_subscription_id=renew_subscription_id),
    )
    items = [
        PublicPlanResponse.model_validate(plan, from_attributes=True) for plan in catalog.plans
    ]
    return PublicPlanListResponse(
        items=items, total=len(items), anchor_currency=catalog.anchor_currency
    )


own_router = APIRouter(prefix="/subscriptions/me", tags=["subscriptions"])


@own_router.get("", response_model=OwnSubscriptionListResponse)
@inject
async def list_own_subscriptions(
    use_case: FromDishka[ListOwnSubscriptionsUsageUseCase],
    config: FromDishka[AppConfig],
    actor: UserDto = Depends(get_current_user),
) -> OwnSubscriptionListResponse:
    secret = config.jwt_secret.get_secret_value()
    items = [
        OwnSubscriptionResponse.from_dto(r.subscription, secret=secret, used_traffic=r.used_traffic)
        for r in await use_case(actor)
    ]
    return OwnSubscriptionListResponse(items=items, total=len(items))


@own_router.get("/trial", response_model=TrialResponse)
@inject
async def get_own_trial(
    use_case: FromDishka[GetAvailableTrialUseCase],
    actor: UserDto = Depends(get_current_user),
) -> TrialResponse:
    trial = await use_case(actor)
    if trial.plan is None:
        return TrialResponse(is_available=False)
    return TrialResponse(
        is_available=trial.is_trial_available,
        plan_id=trial.plan.id,
        plan_name=trial.plan.name,
        duration_days=trial.plan.sellable_durations()[0].days,
        is_free=trial.is_free,
        price=trial.price,
        currency=trial.currency,
        prices=[PublicPlanPriceResponse(currency=p.currency, price=p.price) for p in trial.prices],
    )


@own_router.post(
    "/actions/activate-trial",
    response_model=OwnSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 503),
)
@inject
async def activate_own_trial(
    activate: FromDishka[ActivateTrialSubscriptionUseCase],
    config: FromDishka[AppConfig],
    body: Optional[ActivateTrialRequest] = None,
    actor: UserDto = Depends(get_current_user),
) -> OwnSubscriptionResponse:
    data = ActivateTrialDto(mini_app=body is not None and body.mini_app)
    return OwnSubscriptionResponse.from_dto(
        await activate(actor, data), secret=config.jwt_secret.get_secret_value()
    )


@own_router.get(
    "/{subscription_id:int}/devices",
    response_model=DeviceListResponse,
    responses=error_responses(400, 503),
)
@inject
async def list_own_devices(
    subscription_id: int,
    use_case: FromDishka[ListDevicesUseCase],
    actor: UserDto = Depends(get_current_user),
) -> DeviceListResponse:
    devices = await use_case(actor, SubscriptionRefDto(subscription_id=subscription_id))
    return DeviceListResponse(
        items=[DeviceResponse.model_validate(d, from_attributes=True) for d in devices],
        total=len(devices),
    )


@own_router.delete(
    "/{subscription_id:int}/devices/{hwid}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(400, 503),
)
@inject
async def delete_own_device(
    subscription_id: int,
    hwid: str,
    use_case: FromDishka[DeleteDeviceUseCase],
    actor: UserDto = Depends(get_current_user),
) -> None:
    await use_case(actor, DeleteDeviceDto(subscription_id=subscription_id, hwid=hwid))


@own_router.post(
    "/{subscription_id:int}/devices/bulk/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(400, 503),
)
@inject
async def delete_all_own_devices(
    subscription_id: int,
    use_case: FromDishka[DeleteAllDevicesUseCase],
    actor: UserDto = Depends(get_current_user),
) -> None:
    await use_case(actor, SubscriptionRefDto(subscription_id=subscription_id))


@own_router.post(
    "/{subscription_id:int}/actions/reissue",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(400, 503),
)
@inject
async def reissue_own_subscription(
    subscription_id: int,
    use_case: FromDishka[ReissueSubscriptionUseCase],
    actor: UserDto = Depends(get_current_user),
) -> None:
    await use_case(actor, SubscriptionRefDto(subscription_id=subscription_id))
