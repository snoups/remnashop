from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.modules.loyalty.api.schemas import (
    LoyaltySettingsRequest,
    LoyaltySettingsResponse,
    LoyaltyTierSchema,
    UserLoyaltyRequest,
    UserLoyaltyResponse,
)
from app.modules.loyalty.dto import (
    LoyaltySettingsDto,
    LoyaltyTierDto,
    SetUserLoyaltyExcludedDto,
    UpdateLoyaltySettingsDto,
    UserLoyaltyDto,
)
from app.modules.loyalty.usecases import (
    GetLoyaltySettingsUseCase,
    GetUserLoyaltyUseCase,
    SetUserLoyaltyExcludedUseCase,
    UpdateLoyaltySettingsUseCase,
)

router = APIRouter(tags=["loyalty"])


def _settings_response(settings: LoyaltySettingsDto) -> LoyaltySettingsResponse:
    return LoyaltySettingsResponse(
        enabled=settings.enabled,
        window_months=settings.window_months,
        tiers=[LoyaltyTierSchema(threshold=t.threshold, percent=t.percent) for t in settings.tiers],
        currency=settings.anchor_currency,
    )


def _user_response(loyalty: UserLoyaltyDto) -> UserLoyaltyResponse:
    tier = loyalty.next_tier
    return UserLoyaltyResponse(
        discount=loyalty.discount,
        excluded=loyalty.excluded,
        spent=loyalty.spent,
        next_tier=(
            LoyaltyTierSchema(threshold=tier.threshold, percent=tier.percent) if tier else None
        ),
        currency=loyalty.currency,
    )


@router.get("/loyalty/settings", response_model=LoyaltySettingsResponse)
@inject
async def get_loyalty_settings(
    use_case: FromDishka[GetLoyaltySettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> LoyaltySettingsResponse:
    return _settings_response(await use_case(actor))


@router.put(
    "/loyalty/settings", response_model=LoyaltySettingsResponse, responses=error_responses(400)
)
@inject
async def update_loyalty_settings(
    payload: LoyaltySettingsRequest,
    use_case: FromDishka[UpdateLoyaltySettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> LoyaltySettingsResponse:
    saved = await use_case(
        actor,
        UpdateLoyaltySettingsDto(
            enabled=payload.enabled,
            window_months=payload.window_months,
            tiers=[LoyaltyTierDto(threshold=t.threshold, percent=t.percent) for t in payload.tiers],
        ),
    )
    return _settings_response(saved)


@router.get(
    "/users/{user_id:int}/loyalty",
    response_model=UserLoyaltyResponse,
    responses=error_responses(404),
)
@inject
async def get_user_loyalty(
    user_id: int,
    use_case: FromDishka[GetUserLoyaltyUseCase],
    actor: Actor = Depends(require_admin),
) -> UserLoyaltyResponse:
    return _user_response(await use_case(actor, user_id))


@router.patch(
    "/users/{user_id:int}/loyalty",
    response_model=UserLoyaltyResponse,
    responses=error_responses(400, 404),
)
@inject
async def update_user_loyalty(
    user_id: int,
    payload: UserLoyaltyRequest,
    use_case: FromDishka[SetUserLoyaltyExcludedUseCase],
    actor: Actor = Depends(require_admin),
) -> UserLoyaltyResponse:
    result = await use_case(
        actor, SetUserLoyaltyExcludedDto(user_id=user_id, excluded=payload.excluded)
    )
    return _user_response(result)
