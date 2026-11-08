from typing import Final, Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Body, Depends, Query, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, SEARCH_MAX_LENGTH
from app.core.enums import SubscriptionStatus
from app.modules.subscriptions.api.schemas import (
    ChangeSubscriptionPlanRequest,
    DeletedSubscriptionsResponse,
    DeviceListResponse,
    DeviceResponse,
    GrantSubscriptionRequest,
    MissingSquadListResponse,
    MissingSquadResponse,
    PanelSquadListResponse,
    PanelSquadResponse,
    PanelSyncDirectionStatusResponse,
    PanelSyncPullRequest,
    PanelSyncPushRequest,
    PanelSyncStatusResponse,
    PushToPanelRequest,
    SubscriptionDetailResponse,
    SubscriptionListItemResponse,
    SubscriptionListStatsResponse,
    SubscriptionPageResponse,
    SubscriptionPanelDiffResponse,
    SubscriptionResponse,
    UpdateSubscriptionRequest,
    UpdateSubscriptionSquadsRequest,
)
from app.modules.subscriptions.dto import (
    AdminDeleteDeviceDto,
    ChangeSubscriptionPlanDto,
    GrantSubscriptionDto,
    ListSubscriptionsDto,
    PushSubscriptionToPanelDto,
    SetSubscriptionEnabledDto,
    SyncFromPanelOptionsDto,
    SyncToPanelOptionsDto,
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
    DeleteUserSubscriptionsUseCase,
    GetPanelSyncStatusUseCase,
    GetSubscriptionListStatsUseCase,
    GetSubscriptionPanelDiffUseCase,
    GetSubscriptionUseCase,
    GrantSubscriptionUseCase,
    ListMissingPanelSquadsUseCase,
    ListPanelSquadsUseCase,
    ListSubscriptionsUseCase,
    PullSubscriptionFromPanelUseCase,
    PushSubscriptionToPanelUseCase,
    ResetSubscriptionTrafficUseCase,
    SetSubscriptionEnabledUseCase,
    StartPanelSyncFromUseCase,
    StartPanelSyncToUseCase,
    UpdateSubscriptionSquadsUseCase,
    UpdateSubscriptionUseCase,
)

# sent as null, these are emptied
_CLEARABLE_FIELDS: Final[frozenset[str]] = frozenset({"tag"})

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
user_router = APIRouter(prefix="/users", tags=["subscriptions"])


@router.get("/panel-sync", response_model=PanelSyncStatusResponse)
@inject
async def get_panel_sync_status(
    use_case: FromDishka[GetPanelSyncStatusUseCase],
    actor: Actor = Depends(require_admin),
) -> PanelSyncStatusResponse:
    return PanelSyncStatusResponse.model_validate(await use_case(actor), from_attributes=True)


@router.post(
    "/panel-sync/actions/pull",
    response_model=PanelSyncDirectionStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=error_responses(409),
)
@inject
async def start_panel_sync_from_panel(
    use_case: FromDishka[StartPanelSyncFromUseCase],
    actor: Actor = Depends(require_admin),
    body: PanelSyncPullRequest = Body(default_factory=PanelSyncPullRequest),
) -> PanelSyncDirectionStatusResponse:
    result = await use_case(
        actor,
        SyncFromPanelOptionsDto(
            adopt_unnamed=body.adopt_unnamed,
            respect_subscription_limit=body.respect_subscription_limit,
        ),
    )
    return PanelSyncDirectionStatusResponse.model_validate(result, from_attributes=True)


@router.post(
    "/panel-sync/actions/push",
    response_model=PanelSyncDirectionStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=error_responses(409),
)
@inject
async def start_panel_sync_to_panel(
    use_case: FromDishka[StartPanelSyncToUseCase],
    actor: Actor = Depends(require_admin),
    body: PanelSyncPushRequest = Body(default_factory=PanelSyncPushRequest),
) -> PanelSyncDirectionStatusResponse:
    result = await use_case(
        actor,
        SyncToPanelOptionsDto(
            recreate_missing=body.recreate_missing,
            delete_orphans=body.delete_orphans,
            squad_replacements=body.squad_replacements,
        ),
    )
    return PanelSyncDirectionStatusResponse.model_validate(result, from_attributes=True)


@router.get(
    "/panel-sync/missing-squads",
    response_model=MissingSquadListResponse,
    responses=error_responses(503),
)
@inject
async def list_missing_panel_squads(
    use_case: FromDishka[ListMissingPanelSquadsUseCase],
    actor: Actor = Depends(require_admin),
) -> MissingSquadListResponse:
    items = await use_case(actor)
    return MissingSquadListResponse(
        items=[MissingSquadResponse.model_validate(i, from_attributes=True) for i in items],
        total=len(items),
    )


@router.get("/summary", response_model=SubscriptionListStatsResponse)
@inject
async def get_subscription_list_stats(
    use_case: FromDishka[GetSubscriptionListStatsUseCase],
    actor: Actor = Depends(require_admin),
) -> SubscriptionListStatsResponse:
    return SubscriptionListStatsResponse.model_validate(await use_case(actor), from_attributes=True)


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
    items, total = await use_case(
        actor,
        ListSubscriptionsDto(
            status=status_filter, search=search, user_id=user_id, page=page, page_size=page_size
        ),
    )
    return SubscriptionPageResponse(
        items=[
            SubscriptionListItemResponse.model_validate(
                item.subscription, from_attributes=True
            ).model_copy(update={"user_name": item.user_name})
            for item in items
        ],
        total=total,
    )


@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 404, 503),
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
    responses=error_responses(400, 404, 503),
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
            cleared=frozenset(
                name
                for name in _CLEARABLE_FIELDS & payload.model_fields_set
                if getattr(payload, name) is None
            ),
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
    responses=error_responses(400, 404, 503),
)
@inject
async def delete_subscription(
    subscription_id: int,
    use_case: FromDishka[DeleteSubscriptionUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, subscription_id)


@user_router.post(
    "/{user_id:int}/subscriptions/bulk/delete",
    response_model=DeletedSubscriptionsResponse,
    responses=error_responses(404, 503),
)
@inject
async def delete_user_subscriptions(
    user_id: int,
    use_case: FromDishka[DeleteUserSubscriptionsUseCase],
    actor: Actor = Depends(require_admin),
) -> DeletedSubscriptionsResponse:
    return DeletedSubscriptionsResponse.model_validate(
        await use_case(actor, user_id), from_attributes=True
    )


@router.get(
    "/{subscription_id:int}",
    response_model=SubscriptionDetailResponse,
    responses=error_responses(404),
)
@inject
async def get_subscription(
    subscription_id: int,
    use_case: FromDishka[GetSubscriptionUseCase],
    actor: Actor = Depends(require_admin),
) -> SubscriptionDetailResponse:
    details = await use_case(actor, subscription_id)
    return SubscriptionDetailResponse.model_validate(
        details.subscription, from_attributes=True
    ).model_copy(
        update={
            "used_traffic": details.activity.used_traffic,
            "online_at": details.activity.online_at,
            "sub_last_opened_at": details.activity.sub_last_opened_at,
            "sub_last_user_agent": details.activity.sub_last_user_agent,
        }
    )


@router.post(
    "/{subscription_id:int}/actions/change-plan",
    response_model=SubscriptionResponse,
    responses=error_responses(400, 404, 503),
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
    responses=error_responses(400, 404, 503),
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
    responses=error_responses(400, 404, 503),
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
    responses=error_responses(400, 404, 503),
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
    responses=error_responses(400, 404, 503),
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
    responses=error_responses(400, 404, 503),
)
@inject
async def list_subscription_devices(
    subscription_id: int,
    use_case: FromDishka[AdminListDevicesUseCase],
    actor: Actor = Depends(require_admin),
) -> DeviceListResponse:
    devices = await use_case(actor, subscription_id)
    return DeviceListResponse(
        items=[DeviceResponse.model_validate(device, from_attributes=True) for device in devices],
        total=len(devices),
    )


@router.delete(
    "/{subscription_id:int}/devices/{hwid}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(400, 404, 503),
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
    responses=error_responses(400, 404, 503),
)
@inject
async def delete_all_subscription_devices(
    subscription_id: int,
    use_case: FromDishka[AdminDeleteAllDevicesUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, subscription_id)


@router.get("/squads", response_model=PanelSquadListResponse, responses=error_responses(503))
@inject
async def list_panel_squads(
    use_case: FromDishka[ListPanelSquadsUseCase],
    actor: Actor = Depends(require_admin),
) -> PanelSquadListResponse:
    squads = await use_case(actor)
    return PanelSquadListResponse(
        items=[PanelSquadResponse.model_validate(s, from_attributes=True) for s in squads],
        total=len(squads),
    )


@router.get(
    "/{subscription_id:int}/panel-diff",
    response_model=SubscriptionPanelDiffResponse,
    responses=error_responses(400, 404, 503),
)
@inject
async def get_subscription_panel_diff(
    subscription_id: int,
    use_case: FromDishka[GetSubscriptionPanelDiffUseCase],
    actor: Actor = Depends(require_admin),
) -> SubscriptionPanelDiffResponse:
    return SubscriptionPanelDiffResponse.model_validate(
        await use_case(actor, subscription_id), from_attributes=True
    )


@router.post(
    "/{subscription_id:int}/actions/pull-from-panel",
    response_model=SubscriptionResponse,
    responses=error_responses(400, 404, 503),
)
@inject
async def pull_subscription_from_panel(
    subscription_id: int,
    use_case: FromDishka[PullSubscriptionFromPanelUseCase],
    actor: Actor = Depends(require_admin),
) -> SubscriptionResponse:
    return SubscriptionResponse.model_validate(
        await use_case(actor, subscription_id), from_attributes=True
    )


@router.post(
    "/{subscription_id:int}/actions/push-to-panel",
    response_model=SubscriptionResponse,
    responses=error_responses(400, 404, 503),
)
@inject
async def push_subscription_to_panel(
    subscription_id: int,
    use_case: FromDishka[PushSubscriptionToPanelUseCase],
    actor: Actor = Depends(require_admin),
    body: PushToPanelRequest = Body(default_factory=PushToPanelRequest),
) -> SubscriptionResponse:
    result = await use_case(
        actor,
        PushSubscriptionToPanelDto(
            subscription_id=subscription_id, squad_replacements=body.squad_replacements
        ),
    )
    return SubscriptionResponse.model_validate(result, from_attributes=True)
