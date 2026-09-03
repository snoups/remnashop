from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.admin import require_admin
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.referrals.api.schemas import (
    AdjustPointsRequest,
    ReferralRewardResponse,
    ReferralSettingsResponse,
    ReferralStatsResponse,
    UpdateReferralSettingsRequest,
)
from app.modules.referrals.dto import (
    ReferralSettingsDto,
    ReferralStatsDto,
    UpdateReferralSettingsDto,
)
from app.modules.referrals.usecases.adjust_user_points import (
    AdjustUserPointsDto,
    AdjustUserPointsUseCase,
)
from app.modules.referrals.usecases.get_referral_settings import GetReferralSettingsUseCase
from app.modules.referrals.usecases.get_user_referral_stats import GetUserReferralStatsUseCase
from app.modules.referrals.usecases.update_referral_settings import UpdateReferralSettingsUseCase
from app.modules.users import UserDto

router = APIRouter(tags=["referrals"])


def _settings_to_response(dto: ReferralSettingsDto) -> ReferralSettingsResponse:
    return ReferralSettingsResponse(
        enabled=dto.enabled,
        max_level=dto.max_level,
        accrual_strategy=dto.accrual_strategy,
        reward_type=dto.reward_type,
        reward_amounts=dto.reward_amounts,
    )


def _stats_to_response(dto: ReferralStatsDto) -> ReferralStatsResponse:
    return ReferralStatsResponse(
        referral_code=dto.referral_code,
        referrer_id=dto.referrer_id,
        points=dto.points,
        counts_by_level=dto.counts_by_level,
        rewards=[
            ReferralRewardResponse(type=r.type, amount=r.amount, created_at=r.created_at)
            for r in dto.rewards
        ],
    )


@router.get("/referrals/settings", response_model=ReferralSettingsResponse)
@inject
async def get_referral_settings(
    use_case: FromDishka[GetReferralSettingsUseCase],
    actor: UserDto = Depends(require_admin),
) -> ReferralSettingsResponse:
    return _settings_to_response(await use_case(actor))


@router.put("/referrals/settings", response_model=ReferralSettingsResponse)
@inject
async def update_referral_settings(
    payload: UpdateReferralSettingsRequest,
    use_case: FromDishka[UpdateReferralSettingsUseCase],
    actor: UserDto = Depends(require_admin),
) -> ReferralSettingsResponse:
    updated = await use_case(
        actor,
        UpdateReferralSettingsDto(
            enabled=payload.enabled,
            max_level=payload.max_level,
            accrual_strategy=payload.accrual_strategy,
            reward_type=payload.reward_type,
            reward_amounts=payload.reward_amounts,
        ),
    )
    return _settings_to_response(updated)


@router.get("/users/{user_id}/referrals", response_model=ReferralStatsResponse)
@inject
async def get_user_referral_stats(
    user_id: int,
    use_case: FromDishka[GetUserReferralStatsUseCase],
    actor: UserDto = Depends(require_admin),
) -> ReferralStatsResponse:
    try:
        stats = await use_case(actor, user_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _stats_to_response(stats)


@router.post("/users/{user_id}/points", response_model=ReferralStatsResponse)
@inject
async def adjust_user_points(
    user_id: int,
    payload: AdjustPointsRequest,
    adjust_use_case: FromDishka[AdjustUserPointsUseCase],
    stats_use_case: FromDishka[GetUserReferralStatsUseCase],
    actor: UserDto = Depends(require_admin),
) -> ReferralStatsResponse:
    try:
        await adjust_use_case(actor, AdjustUserPointsDto(user_id=user_id, delta=payload.delta))
        stats = await stats_use_case(actor, user_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _stats_to_response(stats)
