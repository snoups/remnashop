from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from app.api.dependencies.public import get_current_actor
from app.core.actor import Actor
from app.modules.plans.api.schemas import (
    PublicPlanListResponse,
    PublicPlanResponse,
    to_public_duration_items,
)
from app.modules.plans.dto import PlanDto
from app.modules.plans.usecases import ListActivePlansUseCase
from app.modules.pricing import CurrencyRateTable, PricingRepository

router = APIRouter(prefix="/plans", tags=["plans"])


def _to_response(plan: PlanDto, rates: CurrencyRateTable) -> PublicPlanResponse:
    return PublicPlanResponse(
        id=plan.id,
        public_code=plan.public_code,
        name=plan.name,
        description=plan.description,
        tag=plan.tag,
        type=plan.type,
        traffic_limit_strategy=plan.traffic_limit_strategy,
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        is_trial=plan.is_trial,
        order_index=plan.order_index,
        durations=to_public_duration_items(plan.durations, rates),
    )


@router.get("/catalog", response_model=PublicPlanListResponse)
@inject
async def list_active_plans(
    use_case: FromDishka[ListActivePlansUseCase],
    pricing_repository: FromDishka[PricingRepository],
    actor: Actor = Depends(get_current_actor),
) -> PublicPlanListResponse:
    plans = await use_case(actor)
    rates = await pricing_repository.get_rate_table()
    items = [_to_response(plan, rates) for plan in plans]
    return PublicPlanListResponse(items=items, total=len(items))
