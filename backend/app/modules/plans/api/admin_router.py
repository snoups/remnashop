from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.admin import require_admin
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.plans.api.schemas import (
    CreatePlanRequest,
    PlanResponse,
    ReorderPlansRequest,
    SetPlanDurationsRequest,
    UpdatePlanAccessRequest,
    UpdatePlanRequest,
    UpdatePlanSquadsRequest,
    to_duration_items,
)
from app.modules.plans.dto import (
    CreatePlanDto,
    PlanDto,
    ReorderPlansDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    SetPlanPriceDto,
    UpdatePlanAccessDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.usecases import (
    CreatePlanUseCase,
    DeletePlanUseCase,
    ListPlansUseCase,
    ReorderPlansUseCase,
    SetPlanDurationsUseCase,
    UpdatePlanAccessUseCase,
    UpdatePlanSquadsUseCase,
    UpdatePlanUseCase,
)
from app.modules.users import UserDto

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


@router.get("", response_model=list[PlanResponse])
@inject
async def list_plans(
    use_case: FromDishka[ListPlansUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[PlanResponse]:
    plans = await use_case(actor)
    return [_to_response(plan) for plan in plans]


@router.post("", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_plan(
    payload: CreatePlanRequest,
    use_case: FromDishka[CreatePlanUseCase],
    actor: UserDto = Depends(require_admin),
) -> PlanResponse:
    try:
        plan = await use_case(
            actor,
            CreatePlanDto(
                public_code=payload.public_code,
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
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _to_response(plan)


@router.put("/order", response_model=list[PlanResponse])
@inject
async def reorder_plans(
    payload: ReorderPlansRequest,
    use_case: FromDishka[ReorderPlansUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[PlanResponse]:
    try:
        plans = await use_case(actor, ReorderPlansDto(plan_ids=payload.plan_ids))
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return [_to_response(plan) for plan in plans]


@router.put("/{plan_id}", response_model=PlanResponse)
@inject
async def update_plan(
    plan_id: int,
    payload: UpdatePlanRequest,
    use_case: FromDishka[UpdatePlanUseCase],
    actor: UserDto = Depends(require_admin),
) -> PlanResponse:
    try:
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
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _to_response(plan)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_plan(
    plan_id: int,
    use_case: FromDishka[DeletePlanUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    try:
        await use_case(actor, plan_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.put("/{plan_id}/durations", response_model=PlanResponse)
@inject
async def set_plan_durations(
    plan_id: int,
    payload: SetPlanDurationsRequest,
    use_case: FromDishka[SetPlanDurationsUseCase],
    actor: UserDto = Depends(require_admin),
) -> PlanResponse:
    try:
        plan = await use_case(
            actor,
            SetPlanDurationsDto(
                plan_id=plan_id,
                durations=[
                    SetPlanDurationDto(
                        days=duration.days,
                        order_index=duration.order_index,
                        prices=[
                            SetPlanPriceDto(currency=price.currency, price=price.price)
                            for price in duration.prices
                        ],
                    )
                    for duration in payload.durations
                ],
            ),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _to_response(plan)


@router.put("/{plan_id}/access", response_model=PlanResponse)
@inject
async def update_plan_access(
    plan_id: int,
    payload: UpdatePlanAccessRequest,
    use_case: FromDishka[UpdatePlanAccessUseCase],
    actor: UserDto = Depends(require_admin),
) -> PlanResponse:
    try:
        plan = await use_case(
            actor,
            UpdatePlanAccessDto(
                plan_id=plan_id,
                availability=payload.availability,
                allowed_telegram_ids=payload.allowed_telegram_ids,
                allowed_emails=payload.allowed_emails,
            ),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _to_response(plan)


@router.put("/{plan_id}/squads", response_model=PlanResponse)
@inject
async def update_plan_squads(
    plan_id: int,
    payload: UpdatePlanSquadsRequest,
    use_case: FromDishka[UpdatePlanSquadsUseCase],
    actor: UserDto = Depends(require_admin),
) -> PlanResponse:
    try:
        plan = await use_case(
            actor,
            UpdatePlanSquadsDto(
                plan_id=plan_id,
                internal_squads=payload.internal_squads,
                external_squad=payload.external_squad,
            ),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _to_response(plan)
