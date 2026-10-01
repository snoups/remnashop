from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from app.api.dependencies.public import get_current_user
from app.api.dependencies.rate_limit import rate_limit
from app.api.errors import error_responses
from app.core.constants import TIME_1M
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


@router.post(
    "/activations",
    response_model=PublicPromocodeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(key="promocode_activate", limit=10, window_seconds=TIME_1M))],
    responses=error_responses(400, 404, 503),
)
@inject
async def activate_promocode(
    payload: ActivatePromocodeRequest,
    use_case: FromDishka[ActivatePromocodeUseCase],
    actor: UserDto = Depends(get_current_user),
) -> PublicPromocodeResponse:
    promo = await use_case(
        actor,
        ActivatePromocodeDto(
            code=payload.code, target_subscription_id=payload.target_subscription_id
        ),
    )
    return _to_response(promo)
