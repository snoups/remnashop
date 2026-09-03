from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.admin import require_admin
from app.core.enums import Currency, SubscriptionStatus
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    RemnawavePanelUnavailableError,
    ValidationError,
)
from app.modules.pricing import PricingRepository
from app.modules.subscriptions.api.schemas import (
    AddOnEntitlementItem,
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
from app.modules.users import UserDto

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
    actor: UserDto = Depends(require_admin),
    status_filter: Optional[SubscriptionStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> SubscriptionPageResponse:
    subscriptions, total = await use_case(
        actor, ListSubscriptionsInput(status=status_filter, page=page, page_size=page_size)
    )
    return SubscriptionPageResponse(
        items=[_to_subscription_response(subscription) for subscription in subscriptions],
        total=total,
    )


@router.put("/{subscription_id}", response_model=SubscriptionResponse)
@inject
async def update_subscription(
    subscription_id: int,
    payload: UpdateSubscriptionRequest,
    use_case: FromDishka[UpdateSubscriptionUseCase],
    actor: UserDto = Depends(require_admin),
) -> SubscriptionResponse:
    try:
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
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except RemnawavePanelUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Remnawave panel is temporarily unavailable",
        ) from error
    return _to_subscription_response(subscription)


@router.put("/{subscription_id}/squads", response_model=SubscriptionResponse)
@inject
async def update_subscription_squads(
    subscription_id: int,
    payload: UpdateSubscriptionSquadsRequest,
    use_case: FromDishka[UpdateSubscriptionSquadsUseCase],
    actor: UserDto = Depends(require_admin),
) -> SubscriptionResponse:
    try:
        subscription = await use_case(
            actor,
            UpdateSubscriptionSquadsDto(
                subscription_id=subscription_id,
                internal_squads=payload.internal_squads,
                external_squad=payload.external_squad,
            ),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except RemnawavePanelUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Remnawave panel is temporarily unavailable",
        ) from error
    return _to_subscription_response(subscription)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_subscription(
    subscription_id: int,
    use_case: FromDishka[DeleteSubscriptionUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    try:
        await use_case(actor, subscription_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except RemnawavePanelUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Remnawave panel is temporarily unavailable",
        ) from error


@addons_router.get("", response_model=list[AddOnResponse])
@inject
async def list_addons(
    use_case: FromDishka[ListAddOnsUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[AddOnResponse]:
    addons = await use_case(actor)
    return [_to_addon_response(addon) for addon in addons]


@addons_router.post("", response_model=AddOnResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_addon(
    payload: CreateAddOnRequest,
    use_case: FromDishka[CreateAddOnUseCase],
    actor: UserDto = Depends(require_admin),
) -> AddOnResponse:
    try:
        addon = await use_case(
            actor,
            CreateAddOnDto(
                name=payload.name,
                type=payload.type,
                amount=payload.amount,
                base_price=payload.base_price,
            ),
        )
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _to_addon_response(addon)


@addons_router.put("/order", response_model=list[AddOnResponse])
@inject
async def reorder_addons(
    payload: ReorderAddOnsRequest,
    use_case: FromDishka[ReorderAddOnsUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[AddOnResponse]:
    try:
        addons = await use_case(actor, ReorderAddOnsDto(addon_ids=payload.addon_ids))
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return [_to_addon_response(addon) for addon in addons]


@addons_router.put("/{addon_id}", response_model=AddOnResponse)
@inject
async def update_addon(
    addon_id: int,
    payload: UpdateAddOnRequest,
    use_case: FromDishka[UpdateAddOnUseCase],
    actor: UserDto = Depends(require_admin),
) -> AddOnResponse:
    try:
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
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _to_addon_response(addon)


@addons_router.delete("/{addon_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_addon(
    addon_id: int,
    use_case: FromDishka[DeleteAddOnUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    try:
        await use_case(actor, addon_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@addons_router.put("/{addon_id}/base-price", response_model=AddOnResponse)
@inject
async def set_addon_base_price(
    addon_id: int,
    payload: SetAddOnBasePriceRequest,
    use_case: FromDishka[SetAddOnBasePriceUseCase],
    actor: UserDto = Depends(require_admin),
) -> AddOnResponse:
    try:
        addon = await use_case(
            actor, SetAddOnBasePriceDto(addon_id=addon_id, base_price=payload.base_price)
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _to_addon_response(addon)


@addons_router.put("/{addon_id}/override/{currency}", response_model=AddOnResponse)
@inject
async def set_addon_price_override(
    addon_id: int,
    currency: Currency,
    payload: SetAddOnPriceOverrideRequest,
    use_case: FromDishka[SetAddOnPriceOverrideUseCase],
    pricing_repository: FromDishka[PricingRepository],
    actor: UserDto = Depends(require_admin),
) -> AddOnResponse:
    table = await pricing_repository.get_rate_table()
    try:
        addon = await use_case(
            actor,
            SetAddOnPriceOverrideDto(
                addon_id=addon_id, currency=currency, price=payload.price, anchor=table.anchor
            ),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _to_addon_response(addon)
