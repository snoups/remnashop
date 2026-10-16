from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from app.api.dependencies.public import get_current_user
from app.modules.subscriptions.api.schemas import PublicPlanListResponse, PublicPlanResponse
from app.modules.subscriptions.usecases import ListActivePlansUseCase
from app.modules.users import UserDto

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/catalog", response_model=PublicPlanListResponse)
@inject
async def list_active_plans(
    use_case: FromDishka[ListActivePlansUseCase],
    actor: UserDto = Depends(get_current_user),
) -> PublicPlanListResponse:
    catalog = await use_case(actor)
    items = [
        PublicPlanResponse.model_validate(plan, from_attributes=True) for plan in catalog.plans
    ]
    return PublicPlanListResponse(
        items=items, total=len(items), anchor_currency=catalog.anchor_currency
    )
