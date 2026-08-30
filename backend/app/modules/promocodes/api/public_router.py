from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.public import get_current_actor
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.promocodes.api.schemas import ActivatePromocodeRequest, PublicPromocodeResponse
from app.modules.promocodes.dto import ActivatePromocodeDto, PromocodeDto
from app.modules.promocodes.usecases import ActivatePromocodeUseCase
from app.modules.users import UserDto

router = APIRouter(prefix="/promocodes", tags=["promocodes"])


def _to_response(promo: PromocodeDto) -> PublicPromocodeResponse:
    return PublicPromocodeResponse(
        code=promo.code,
        reward_type=promo.reward_type,
        reward=promo.reward,
        reward_addon_id=promo.reward_addon_id,
        reward_plan_id=promo.reward_plan_id,
        reward_duration_days=promo.reward_duration_days,
    )


@router.post("/activate", response_model=PublicPromocodeResponse)
@inject
async def activate_promocode(
    payload: ActivatePromocodeRequest,
    use_case: FromDishka[ActivatePromocodeUseCase],
    actor: UserDto = Depends(get_current_actor),
) -> PublicPromocodeResponse:
    try:
        promo = await use_case(
            actor,
            ActivatePromocodeDto(
                code=payload.code, target_subscription_id=payload.target_subscription_id
            ),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _to_response(promo)
