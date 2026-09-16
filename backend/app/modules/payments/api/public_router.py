from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.public import get_current_user
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.modules.payments.api.schemas import CheckoutResponse, CreateCheckoutRequest
from app.modules.payments.dto import CreateCheckoutDto
from app.modules.payments.usecases.create_checkout import CreateCheckoutUseCase
from app.modules.users import UserDto

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/checkout", response_model=CheckoutResponse)
@inject
async def create_checkout(
    payload: CreateCheckoutRequest,
    use_case: FromDishka[CreateCheckoutUseCase],
    actor: UserDto = Depends(get_current_user),
) -> CheckoutResponse:
    try:
        result = await use_case(
            actor,
            CreateCheckoutDto(
                user_id=actor.id,
                plan_id=payload.plan_id,
                duration_days=payload.duration_days,
                currency=payload.currency,
                purchase_type=payload.purchase_type,
                gateway_type=payload.gateway_type,
                target_subscription_id=payload.target_subscription_id,
                customer_email=payload.customer_email,
            ),
        )
    except PermissionDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return CheckoutResponse(order_id=result.order_id, confirmation_url=result.confirmation_url)
