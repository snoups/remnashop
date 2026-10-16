from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import Currency
from app.modules.plans.api.schemas import (
    AddOnListResponse,
    AddOnResponse,
    AdjustBasePricesRequest,
    CreateAddOnRequest,
    CreatePlanRequest,
    PlanListResponse,
    PlanResponse,
    PlanShareUrlsResponse,
    PreviewPricingChangeRequest,
    PriceBookResponse,
    PricingDiffResponse,
    PricingSettingsResponse,
    ReorderPlansRequest,
    SetAddOnBasePriceRequest,
    SetAddOnPriceOverrideRequest,
    SetPlanDurationBasePriceRequest,
    SetPlanDurationsRequest,
    SetPlanPriceOverrideRequest,
    SwitchAnchorRequest,
    UpdateAddOnRequest,
    UpdateCurrencyRateRequest,
    UpdatePlanAccessRequest,
    UpdatePlanDiscountRequest,
    UpdatePlanRequest,
    UpdatePlanSquadsRequest,
    UpdatePricingSettingsRequest,
)
from app.modules.plans.dto import (
    AdjustBasePricesDto,
    CreateAddOnDto,
    CreatePlanDto,
    PricingChangePreviewDto,
    ReorderPlansDto,
    SetAddOnBasePriceDto,
    SetAddOnPriceOverrideDto,
    SetPlanDurationBasePriceDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    SetPlanPriceOverrideDto,
    SwitchAnchorCurrencyDto,
    UpdateAddOnDto,
    UpdatePlanAccessDto,
    UpdatePlanDiscountDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.usecases import (
    AdjustBasePricesUseCase,
    CreateAddOnUseCase,
    CreatePlanUseCase,
    DeleteAddOnUseCase,
    DeletePlanUseCase,
    GetAddOnUseCase,
    GetPlanShareUrlsUseCase,
    GetPlanUseCase,
    GetPriceBookUseCase,
    ListAddOnsUseCase,
    ListPlansUseCase,
    PreviewPricingChangeUseCase,
    ReorderPlansUseCase,
    SetAddOnBasePriceUseCase,
    SetAddOnPriceOverrideUseCase,
    SetPlanDurationBasePriceUseCase,
    SetPlanDurationsUseCase,
    SetPlanPriceOverrideUseCase,
    SwitchAnchorCurrencyUseCase,
    UpdateAddOnUseCase,
    UpdatePlanAccessUseCase,
    UpdatePlanDiscountUseCase,
    UpdatePlanSquadsUseCase,
    UpdatePlanUseCase,
)
from app.modules.pricing import (
    UpdateCurrencyRateDto,
    UpdateCurrencyRateUseCase,
    UpdatePricingSettingsDto,
    UpdatePricingSettingsUseCase,
)

router = APIRouter(prefix="/plans", tags=["plans"])
addons_router = APIRouter(prefix="/addons", tags=["addons"])
pricing_router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("", response_model=PlanListResponse)
@inject
async def list_plans(
    use_case: FromDishka[ListPlansUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanListResponse:
    plans = await use_case(actor)
    items = [PlanResponse.model_validate(plan, from_attributes=True) for plan in plans]
    return PlanListResponse(items=items, total=len(items))


@router.post(
    "",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409),
)
@inject
async def create_plan(
    payload: CreatePlanRequest,
    use_case: FromDishka[CreatePlanUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanResponse:
    plan = await use_case(
        actor,
        CreatePlanDto(
            name=payload.name,
            description=payload.description,
            tag=payload.tag,
            type=payload.type,
            traffic_limit_strategy=payload.traffic_limit_strategy,
            traffic_limit=payload.traffic_limit,
            device_limit=payload.device_limit,
            is_trial=payload.is_trial,
            allow_bonus_days=payload.allow_bonus_days,
            allow_promocodes=payload.allow_promocodes,
        ),
    )
    return PlanResponse.model_validate(plan, from_attributes=True)


@router.post("/actions/reorder", response_model=PlanListResponse, responses=error_responses(400))
@inject
async def reorder_plans(
    payload: ReorderPlansRequest,
    use_case: FromDishka[ReorderPlansUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanListResponse:
    plans = await use_case(actor, ReorderPlansDto(plan_ids=payload.plan_ids))
    items = [PlanResponse.model_validate(plan, from_attributes=True) for plan in plans]
    return PlanListResponse(items=items, total=len(items))


@router.patch("/{plan_id:int}", response_model=PlanResponse, responses=error_responses(404, 409))
@inject
async def update_plan(
    plan_id: int,
    payload: UpdatePlanRequest,
    use_case: FromDishka[UpdatePlanUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanResponse:
    plan = await use_case(
        actor,
        UpdatePlanDto(
            plan_id=plan_id,
            name=payload.name,
            description=payload.description,
            tag=payload.tag,
            type=payload.type,
            traffic_limit_strategy=payload.traffic_limit_strategy,
            traffic_limit=payload.traffic_limit,
            device_limit=payload.device_limit,
            is_active=payload.is_active,
            is_trial=payload.is_trial,
            allow_bonus_days=payload.allow_bonus_days,
            allow_promocodes=payload.allow_promocodes,
        ),
    )
    return PlanResponse.model_validate(plan, from_attributes=True)


@router.delete(
    "/{plan_id:int}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404, 409)
)
@inject
async def delete_plan(
    plan_id: int,
    use_case: FromDishka[DeletePlanUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, plan_id)


@router.put(
    "/{plan_id:int}/durations", response_model=PlanResponse, responses=error_responses(400, 404)
)
@inject
async def set_plan_durations(
    plan_id: int,
    payload: SetPlanDurationsRequest,
    use_case: FromDishka[SetPlanDurationsUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanResponse:
    plan = await use_case(
        actor,
        SetPlanDurationsDto(
            plan_id=plan_id,
            durations=[
                SetPlanDurationDto(
                    days=duration.days,
                    order_index=duration.order_index,
                    base_price=duration.base_price,
                )
                for duration in payload.durations
            ],
        ),
    )
    return PlanResponse.model_validate(plan, from_attributes=True)


@router.put(
    "/{plan_id:int}/durations/{days:int}/override/{currency}",
    response_model=PlanResponse,
    responses=error_responses(400, 404),
)
@inject
async def set_plan_price_override(
    plan_id: int,
    days: int,
    currency: Currency,
    payload: SetPlanPriceOverrideRequest,
    use_case: FromDishka[SetPlanPriceOverrideUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanResponse:
    plan = await use_case(
        actor,
        SetPlanPriceOverrideDto(
            plan_id=plan_id,
            days=days,
            currency=currency,
            price=payload.price,
        ),
    )
    return PlanResponse.model_validate(plan, from_attributes=True)


@router.put(
    "/{plan_id:int}/durations/{days:int}/base-price",
    response_model=PlanResponse,
    responses=error_responses(400, 404),
)
@inject
async def set_plan_duration_base_price(
    plan_id: int,
    days: int,
    payload: SetPlanDurationBasePriceRequest,
    use_case: FromDishka[SetPlanDurationBasePriceUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanResponse:
    plan = await use_case(
        actor,
        SetPlanDurationBasePriceDto(plan_id=plan_id, days=days, base_price=payload.base_price),
    )
    return PlanResponse.model_validate(plan, from_attributes=True)


@router.put(
    "/{plan_id:int}/access", response_model=PlanResponse, responses=error_responses(400, 404)
)
@inject
async def update_plan_access(
    plan_id: int,
    payload: UpdatePlanAccessRequest,
    use_case: FromDishka[UpdatePlanAccessUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanResponse:
    plan = await use_case(
        actor,
        UpdatePlanAccessDto(
            plan_id=plan_id,
            availability=payload.availability,
            allowed_telegram_ids=payload.allowed_telegram_ids,
            allowed_emails=payload.allowed_emails,
        ),
    )
    return PlanResponse.model_validate(plan, from_attributes=True)


@router.put("/{plan_id:int}/squads", response_model=PlanResponse, responses=error_responses(404))
@inject
async def update_plan_squads(
    plan_id: int,
    payload: UpdatePlanSquadsRequest,
    use_case: FromDishka[UpdatePlanSquadsUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanResponse:
    plan = await use_case(
        actor,
        UpdatePlanSquadsDto(
            plan_id=plan_id,
            internal_squads=payload.internal_squads,
            external_squad=payload.external_squad,
        ),
    )
    return PlanResponse.model_validate(plan, from_attributes=True)


@router.put(
    "/{plan_id:int}/discount", response_model=PlanResponse, responses=error_responses(400, 404)
)
@inject
async def update_plan_discount(
    plan_id: int,
    payload: UpdatePlanDiscountRequest,
    use_case: FromDishka[UpdatePlanDiscountUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanResponse:
    plan = await use_case(
        actor,
        UpdatePlanDiscountDto(
            plan_id=plan_id,
            discount_percent=payload.discount_percent,
            discount_starts_at=payload.discount_starts_at,
            discount_ends_at=payload.discount_ends_at,
        ),
    )
    return PlanResponse.model_validate(plan, from_attributes=True)


@router.get("/{plan_id:int}", response_model=PlanResponse, responses=error_responses(404))
@inject
async def get_plan(
    plan_id: int,
    use_case: FromDishka[GetPlanUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanResponse:
    return PlanResponse.model_validate(await use_case(actor, plan_id), from_attributes=True)


@router.get(
    "/{plan_id:int}/share", response_model=PlanShareUrlsResponse, responses=error_responses(404)
)
@inject
async def get_plan_share_urls(
    plan_id: int,
    use_case: FromDishka[GetPlanShareUrlsUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanShareUrlsResponse:
    return PlanShareUrlsResponse.model_validate(
        await use_case(actor, plan_id), from_attributes=True
    )


@addons_router.get("", response_model=AddOnListResponse)
@inject
async def list_addons(
    use_case: FromDishka[ListAddOnsUseCase],
    actor: Actor = Depends(require_admin),
) -> AddOnListResponse:
    addons = await use_case(actor)
    items = [AddOnResponse.model_validate(addon, from_attributes=True) for addon in addons]
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
    return AddOnResponse.model_validate(addon, from_attributes=True)


@addons_router.patch(
    "/{addon_id:int}", response_model=AddOnResponse, responses=error_responses(404, 409)
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
    return AddOnResponse.model_validate(addon, from_attributes=True)


@addons_router.delete(
    "/{addon_id:int}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404, 409)
)
@inject
async def delete_addon(
    addon_id: int,
    use_case: FromDishka[DeleteAddOnUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, addon_id)


@addons_router.put(
    "/{addon_id:int}/base-price", response_model=AddOnResponse, responses=error_responses(404)
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
    return AddOnResponse.model_validate(addon, from_attributes=True)


@addons_router.put(
    "/{addon_id:int}/override/{currency}",
    response_model=AddOnResponse,
    responses=error_responses(400, 404),
)
@inject
async def set_addon_price_override(
    addon_id: int,
    currency: Currency,
    payload: SetAddOnPriceOverrideRequest,
    use_case: FromDishka[SetAddOnPriceOverrideUseCase],
    actor: Actor = Depends(require_admin),
) -> AddOnResponse:
    addon = await use_case(
        actor,
        SetAddOnPriceOverrideDto(
            addon_id=addon_id,
            currency=currency,
            price=payload.price,
        ),
    )
    return AddOnResponse.model_validate(addon, from_attributes=True)


@addons_router.get("/{addon_id:int}", response_model=AddOnResponse, responses=error_responses(404))
@inject
async def get_addon(
    addon_id: int,
    use_case: FromDishka[GetAddOnUseCase],
    actor: Actor = Depends(require_admin),
) -> AddOnResponse:
    return AddOnResponse.model_validate(await use_case(actor, addon_id), from_attributes=True)


@pricing_router.get("/book", response_model=PriceBookResponse)
@inject
async def get_price_book(
    use_case: FromDishka[GetPriceBookUseCase],
    actor: Actor = Depends(require_admin),
) -> PriceBookResponse:
    book = await use_case(actor)
    return PriceBookResponse.model_validate(book, from_attributes=True)


@pricing_router.put(
    "/rates/{currency}", response_model=PriceBookResponse, responses=error_responses(400)
)
@inject
async def update_currency_rate(
    currency: Currency,
    payload: UpdateCurrencyRateRequest,
    use_case: FromDishka[UpdateCurrencyRateUseCase],
    price_book_use_case: FromDishka[GetPriceBookUseCase],
    actor: Actor = Depends(require_admin),
) -> PriceBookResponse:
    await use_case(
        actor,
        UpdateCurrencyRateDto(
            currency=currency,
            rate=payload.rate,
            rounding_mode=payload.rounding_mode,
            charm_ending=payload.charm_ending,
            min_amount=payload.min_amount,
        ),
    )
    book = await price_book_use_case(actor)
    return PriceBookResponse.model_validate(book, from_attributes=True)


@pricing_router.patch("/settings", response_model=PricingSettingsResponse)
@inject
async def update_pricing_settings(
    payload: UpdatePricingSettingsRequest,
    use_case: FromDishka[UpdatePricingSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> PricingSettingsResponse:
    settings = await use_case(
        actor,
        UpdatePricingSettingsDto(
            price_per_day=payload.price_per_day, price_per_gb=payload.price_per_gb
        ),
    )
    return PricingSettingsResponse.model_validate(settings, from_attributes=True)


@pricing_router.post(
    "/actions/switch-anchor", response_model=PriceBookResponse, responses=error_responses(400)
)
@inject
async def switch_anchor_currency(
    payload: SwitchAnchorRequest,
    use_case: FromDishka[SwitchAnchorCurrencyUseCase],
    actor: Actor = Depends(require_admin),
) -> PriceBookResponse:
    book = await use_case(actor, SwitchAnchorCurrencyDto(new_anchor=payload.new_anchor))
    return PriceBookResponse.model_validate(book, from_attributes=True)


@pricing_router.post(
    "/actions/preview", response_model=PricingDiffResponse, responses=error_responses(400)
)
@inject
async def preview_pricing_change(
    payload: PreviewPricingChangeRequest,
    use_case: FromDishka[PreviewPricingChangeUseCase],
    actor: Actor = Depends(require_admin),
) -> PricingDiffResponse:
    rate = None
    if payload.rate is not None:
        rate = UpdateCurrencyRateDto(
            currency=payload.rate.currency,
            rate=payload.rate.rate,
            rounding_mode=payload.rate.rounding_mode,
            charm_ending=payload.rate.charm_ending,
            min_amount=payload.rate.min_amount,
        )
    adjust = None
    if payload.adjust is not None:
        adjust = AdjustBasePricesDto(
            scope=payload.adjust.scope,
            factor=payload.adjust.factor,
            plan_duration_ids=payload.adjust.plan_duration_ids,
            addon_ids=payload.adjust.addon_ids,
        )
    diff = await use_case(
        actor, PricingChangePreviewDto(rate=rate, anchor=payload.anchor, adjust=adjust)
    )
    return PricingDiffResponse.model_validate(diff, from_attributes=True)


@pricing_router.post("/actions/adjust-base-prices", response_model=PriceBookResponse)
@inject
async def adjust_base_prices(
    payload: AdjustBasePricesRequest,
    use_case: FromDishka[AdjustBasePricesUseCase],
    actor: Actor = Depends(require_admin),
) -> PriceBookResponse:
    book = await use_case(
        actor,
        AdjustBasePricesDto(
            scope=payload.scope,
            factor=payload.factor,
            plan_duration_ids=payload.plan_duration_ids,
            addon_ids=payload.addon_ids,
        ),
    )
    return PriceBookResponse.model_validate(book, from_attributes=True)
