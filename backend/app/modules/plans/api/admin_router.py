from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import Currency
from app.modules.plans.api.schemas import (
    CreatePlanRequest,
    PlanListResponse,
    PlanResponse,
    ReorderPlansRequest,
    SetPlanDurationBasePriceRequest,
    SetPlanDurationsRequest,
    SetPlanPriceOverrideRequest,
    UpdatePlanAccessRequest,
    UpdatePlanRequest,
    UpdatePlanSquadsRequest,
    to_duration_items,
)
from app.modules.plans.dto import (
    CreatePlanDto,
    PlanDto,
    ReorderPlansDto,
    SetPlanDurationBasePriceDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    SetPlanPriceOverrideDto,
    UpdatePlanAccessDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.usecases import (
    CreatePlanUseCase,
    DeletePlanUseCase,
    GetPlanUseCase,
    ListPlansUseCase,
    ReorderPlansUseCase,
    SetPlanDurationBasePriceUseCase,
    SetPlanDurationsUseCase,
    SetPlanPriceOverrideUseCase,
    UpdatePlanAccessUseCase,
    UpdatePlanSquadsUseCase,
    UpdatePlanUseCase,
)
from app.modules.pricing import PricingRepository

router = APIRouter(prefix="/plans", tags=["plans"])


def _to_response(plan: PlanDto) -> PlanResponse:
    return PlanResponse(
        id=plan.id,
        public_code=plan.public_code,
        name=plan.name,
        description=plan.description,
        tag=plan.tag,
        type=plan.type,
        availability=plan.availability,
        traffic_limit_strategy=plan.traffic_limit_strategy,
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        allowed_telegram_ids=plan.allowed_telegram_ids,
        allowed_emails=plan.allowed_emails,
        internal_squads=plan.internal_squads,
        external_squad=plan.external_squad,
        order_index=plan.order_index,
        is_active=plan.is_active,
        is_trial=plan.is_trial,
        durations=to_duration_items(plan.durations),
    )


@router.get("", response_model=PlanListResponse)
@inject
async def list_plans(
    use_case: FromDishka[ListPlansUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanListResponse:
    plans = await use_case(actor)
    items = [_to_response(plan) for plan in plans]
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
        ),
    )
    return _to_response(plan)


@router.post("/actions/reorder", response_model=PlanListResponse, responses=error_responses(400))
@inject
async def reorder_plans(
    payload: ReorderPlansRequest,
    use_case: FromDishka[ReorderPlansUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanListResponse:
    plans = await use_case(actor, ReorderPlansDto(plan_ids=payload.plan_ids))
    items = [_to_response(plan) for plan in plans]
    return PlanListResponse(items=items, total=len(items))


@router.patch("/{plan_id}", response_model=PlanResponse, responses=error_responses(404, 409))
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
        ),
    )
    return _to_response(plan)


@router.delete(
    "/{plan_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404, 409)
)
@inject
async def delete_plan(
    plan_id: int,
    use_case: FromDishka[DeletePlanUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, plan_id)


@router.put(
    "/{plan_id}/durations", response_model=PlanResponse, responses=error_responses(400, 404)
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
    return _to_response(plan)


@router.put(
    "/{plan_id}/durations/{days}/override/{currency}",
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
    pricing_repository: FromDishka[PricingRepository],
    actor: Actor = Depends(require_admin),
) -> PlanResponse:
    table = await pricing_repository.get_rate_table()
    plan = await use_case(
        actor,
        SetPlanPriceOverrideDto(
            plan_id=plan_id,
            days=days,
            currency=currency,
            price=payload.price,
            anchor=table.anchor,
        ),
    )
    return _to_response(plan)


@router.put(
    "/{plan_id}/durations/{days}/base-price",
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
    return _to_response(plan)


@router.put("/{plan_id}/access", response_model=PlanResponse, responses=error_responses(400, 404))
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
    return _to_response(plan)


@router.put("/{plan_id}/squads", response_model=PlanResponse, responses=error_responses(404))
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
    return _to_response(plan)


@router.get("/{plan_id:int}", response_model=PlanResponse, responses=error_responses(404))
@inject
async def get_plan(
    plan_id: int,
    use_case: FromDishka[GetPlanUseCase],
    actor: Actor = Depends(require_admin),
) -> PlanResponse:
    return _to_response(await use_case(actor, plan_id))
