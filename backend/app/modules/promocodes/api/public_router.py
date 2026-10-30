from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.public import get_current_user
from app.api.dependencies.rate_limit import user_rate_limit
from app.api.errors import error_responses
from app.core.constants import TIME_1M
from app.modules.promocodes.api.schemas import (
    ActivatePromocodeRequest,
    PromocodeTargetsResponse,
    PublicPromocodeResponse,
)
from app.modules.promocodes.dto import ActivatePromocodeDto, ListPromocodeTargetsDto
from app.modules.promocodes.usecases import ActivatePromocodeUseCase, ListPromocodeTargetsUseCase
from app.modules.users import UserDto

router = APIRouter(prefix="/promocodes", tags=["promocodes"])


@router.post(
    "/activations",
    response_model=PublicPromocodeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(user_rate_limit(key="promocode_activate", limit=10, window_seconds=TIME_1M))
    ],
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
    return PublicPromocodeResponse.model_validate(promo, from_attributes=True)


# what a code asking for a subscription can go to: the cabinet's pick list, by
# the activation's own rule; rate-limited like the activation, as it probes codes too
@router.get(
    "/targets",
    response_model=PromocodeTargetsResponse,
    dependencies=[
        Depends(user_rate_limit(key="promocode_targets", limit=10, window_seconds=TIME_1M))
    ],
    responses=error_responses(400, 404),
)
@inject
async def list_promocode_targets(
    use_case: FromDishka[ListPromocodeTargetsUseCase],
    code: str = Query(min_length=1, max_length=64),
    actor: UserDto = Depends(get_current_user),
) -> PromocodeTargetsResponse:
    subscriptions = await use_case(actor, ListPromocodeTargetsDto(code=code))
    return PromocodeTargetsResponse(subscription_ids=[s.id for s in subscriptions])
