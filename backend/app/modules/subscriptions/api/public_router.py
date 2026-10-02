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
    items = [
        PublicPlanResponse.model_validate(plan, from_attributes=True)
        for plan in await use_case(actor)
    ]
    return PublicPlanListResponse(items=items, total=len(items))
