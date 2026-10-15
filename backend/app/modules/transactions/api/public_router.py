from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from app.api.dependencies.public import get_current_user
from app.api.errors import error_responses
from app.modules.transactions.api.schemas import CheckoutResponse, CreateCheckoutRequest
from app.modules.transactions.dto import CreateCheckoutDto
from app.modules.transactions.usecases import CreateCheckoutUseCase
from app.modules.users import UserDto

router = APIRouter(tags=["transactions"])


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 403, 404, 502),
)
@inject
async def create_checkout(
    payload: CreateCheckoutRequest,
    use_case: FromDishka[CreateCheckoutUseCase],
    actor: UserDto = Depends(get_current_user),
) -> CheckoutResponse:
    result = await use_case(
        actor,
        CreateCheckoutDto(
            plan_id=payload.plan_id,
            duration_days=payload.duration_days,
            currency=payload.currency,
            purchase_type=payload.purchase_type,
            gateway_type=payload.gateway_type,
            target_subscription_id=payload.target_subscription_id,
            customer_email=payload.customer_email,
            plan_code=payload.plan_code,
        ),
    )
    return CheckoutResponse.model_validate(result, from_attributes=True)
