from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import Currency, SubscriptionStatus
from app.modules.pricing import PricingRepository
from app.modules.subscriptions.api.schemas import (
    AddOnEntitlementItem,
    AddOnListResponse,
    AddOnPriceItem,
    AddOnResponse,
    CreateAddOnRequest,
    ReorderAddOnsRequest,
    SetAddOnBasePriceRequest,
    SetAddOnPriceOverrideRequest,
    SubscriptionPageResponse,
    SubscriptionResponse,
    UpdateAddOnRequest,
    UpdateSubscriptionRequest,
    UpdateSubscriptionSquadsRequest,
)
from app.modules.subscriptions.dto import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    AddOnDto,
    CreateAddOnDto,
    ReorderAddOnsDto,
    SetAddOnBasePriceDto,
    SetAddOnPriceOverrideDto,
    SubscriptionDto,
    UpdateAddOnDto,
    UpdateSubscriptionDto,
    UpdateSubscriptionSquadsDto,
)
from app.modules.subscriptions.usecases import (
    CreateAddOnUseCase,
    DeleteAddOnUseCase,
    DeleteSubscriptionUseCase,
    GetAddOnUseCase,
    GetSubscriptionUseCase,
    ListAddOnsUseCase,
    ListSubscriptionsInput,
    ListSubscriptionsUseCase,
    ReorderAddOnsUseCase,
    SetAddOnBasePriceUseCase,
    SetAddOnPriceOverrideUseCase,
    UpdateAddOnUseCase,
    UpdateSubscriptionSquadsUseCase,
    UpdateSubscriptionUseCase,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
addons_router = APIRouter(prefix="/addons", tags=["addons"])


def _to_subscription_response(subscription: SubscriptionDto) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=subscription.id,
        user_id=subscription.user_id,
        remnawave_user_id=subscription.remnawave_user_id,
        status=subscription.status,
        is_trial=subscription.is_trial,
        traffic_limit=subscription.traffic_limit,
        device_limit=subscription.device_limit,
        effective_traffic_limit=subscription.effective_traffic_limit,
        effective_device_limit=subscription.effective_device_limit,
        traffic_limit_strategy=subscription.traffic_limit_strategy,
        tag=subscription.tag,
        internal_squads=subscription.internal_squads,
        external_squad=subscription.external_squad,
        expire_at=subscription.expire_at,
        url=subscription.url,
        plan_snapshot=subscription.plan_snapshot.to_json(),
        device_single_reset_at=subscription.device_single_reset_at,
        device_all_reset_at=subscription.device_all_reset_at,
        link_reset_at=subscription.link_reset_at,
        addon_entitlements=[
            AddOnEntitlementItem(
                subscription_id=entitlement.subscription_id,
                addon_id=entitlement.addon_id,
                type=entitlement.type,
                amount=entitlement.amount,
                granted_at=entitlement.granted_at,
            )
            for entitlement in subscription.addon_entitlements
        ],
    )


def _to_addon_response(addon: AddOnDto) -> AddOnResponse:
    return AddOnResponse(
        id=addon.id,
        name=addon.name,
        type=addon.type,
        amount=addon.amount,
        order_index=addon.order_index,
        is_active=addon.is_active,
        base_price=addon.base_price,
        overrides=[
            AddOnPriceItem(currency=override.currency, price=override.price)
            for override in addon.overrides
        ],
    )


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
        ListSubscriptionsInput(
            status=status_filter, search=search, user_id=user_id, page=page, page_size=page_size
        ),
    )
    return SubscriptionPageResponse(
        items=[_to_subscription_response(subscription) for subscription in subscriptions],
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
    return _to_subscription_response(subscription)


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
    return _to_subscription_response(subscription)


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


@addons_router.get("", response_model=AddOnListResponse)
@inject
async def list_addons(
    use_case: FromDishka[ListAddOnsUseCase],
    actor: Actor = Depends(require_admin),
) -> AddOnListResponse:
    addons = await use_case(actor)
    items = [_to_addon_response(addon) for addon in addons]
    return AddOnListResponse(items=items, total=len(items))


@addons_router.post(
    "",
    response_model=AddOnResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409),
)
@inject
async def create_addon(
    payload: CreateAddOnRequest,
    use_case: FromDishka[CreateAddOnUseCase],
    actor: Actor = Depends(require_admin),
) -> AddOnResponse:
    addon = await use_case(
        actor,
        CreateAddOnDto(
            name=payload.name,
            type=payload.type,
            amount=payload.amount,
            base_price=payload.base_price,
        ),
    )
    return _to_addon_response(addon)


@addons_router.post(
    "/actions/reorder", response_model=AddOnListResponse, responses=error_responses(400)
)
@inject
async def reorder_addons(
    payload: ReorderAddOnsRequest,
    use_case: FromDishka[ReorderAddOnsUseCase],
    actor: Actor = Depends(require_admin),
) -> AddOnListResponse:
    addons = await use_case(actor, ReorderAddOnsDto(addon_ids=payload.addon_ids))
    items = [_to_addon_response(addon) for addon in addons]
    return AddOnListResponse(items=items, total=len(items))


@addons_router.patch(
    "/{addon_id}", response_model=AddOnResponse, responses=error_responses(404, 409)
)
@inject
async def update_addon(
    addon_id: int,
    payload: UpdateAddOnRequest,
    use_case: FromDishka[UpdateAddOnUseCase],
    actor: Actor = Depends(require_admin),
) -> AddOnResponse:
    addon = await use_case(
        actor,
        UpdateAddOnDto(
            addon_id=addon_id,
            name=payload.name,
            type=payload.type,
            amount=payload.amount,
            is_active=payload.is_active,
        ),
    )
    return _to_addon_response(addon)


@addons_router.delete(
    "/{addon_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404, 409)
)
@inject
async def delete_addon(
    addon_id: int,
    use_case: FromDishka[DeleteAddOnUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, addon_id)


@addons_router.put(
    "/{addon_id}/base-price", response_model=AddOnResponse, responses=error_responses(404)
)
@inject
async def set_addon_base_price(
    addon_id: int,
    payload: SetAddOnBasePriceRequest,
    use_case: FromDishka[SetAddOnBasePriceUseCase],
    actor: Actor = Depends(require_admin),
) -> AddOnResponse:
    addon = await use_case(
        actor, SetAddOnBasePriceDto(addon_id=addon_id, base_price=payload.base_price)
    )
    return _to_addon_response(addon)


@addons_router.put(
    "/{addon_id}/override/{currency}",
    response_model=AddOnResponse,
    responses=error_responses(400, 404),
)
@inject
async def set_addon_price_override(
    addon_id: int,
    currency: Currency,
    payload: SetAddOnPriceOverrideRequest,
    use_case: FromDishka[SetAddOnPriceOverrideUseCase],
    pricing_repository: FromDishka[PricingRepository],
    actor: Actor = Depends(require_admin),
) -> AddOnResponse:
    table = await pricing_repository.get_rate_table()
    addon = await use_case(
        actor,
        SetAddOnPriceOverrideDto(
            addon_id=addon_id, currency=currency, price=payload.price, anchor=table.anchor
        ),
    )
    return _to_addon_response(addon)


@addons_router.get("/{addon_id:int}", response_model=AddOnResponse, responses=error_responses(404))
@inject
async def get_addon(
    addon_id: int,
    use_case: FromDishka[GetAddOnUseCase],
    actor: Actor = Depends(require_admin),
) -> AddOnResponse:
    return _to_addon_response(await use_case(actor, addon_id))


@router.get(
    "/{subscription_id:int}", response_model=SubscriptionResponse, responses=error_responses(404)
)
@inject
async def get_subscription(
    subscription_id: int,
    use_case: FromDishka[GetSubscriptionUseCase],
    actor: Actor = Depends(require_admin),
) -> SubscriptionResponse:
    return _to_subscription_response(await use_case(actor, subscription_id))
