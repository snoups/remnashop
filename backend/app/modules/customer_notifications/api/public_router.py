from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from app.api.dependencies.public import get_current_user
from app.modules.customer_notifications.api.schemas import CustomerFeedResponse
from app.modules.customer_notifications.usecases import (
    GetCustomerFeedUseCase,
    MarkCustomerFeedReadUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/notifications/me", tags=["notifications"])


@router.get("", response_model=CustomerFeedResponse)
@inject
async def get_my_feed(
    use_case: FromDishka[GetCustomerFeedUseCase],
    actor: UserDto = Depends(get_current_user),
) -> CustomerFeedResponse:
    return CustomerFeedResponse.model_validate(await use_case(actor), from_attributes=True)


@router.post("/actions/mark-read", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def mark_my_feed_read(
    use_case: FromDishka[MarkCustomerFeedReadUseCase],
    actor: UserDto = Depends(get_current_user),
) -> None:
    await use_case(actor)
