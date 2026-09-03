from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.public import get_current_actor
from app.core.exceptions import ValidationError
from app.modules.referrals.api.schemas import (
    AttachReferralRequest,
    ReferralRewardResponse,
    ReferralStatsResponse,
    WithdrawPointsRequest,
)
from app.modules.referrals.dto import ReferralStatsDto
from app.modules.referrals.usecases.attach_referral import AttachReferralDto, AttachReferralUseCase
from app.modules.referrals.usecases.get_own_referral_stats import GetOwnReferralStatsUseCase
from app.modules.referrals.usecases.request_points_withdrawal import (
    RequestPointsWithdrawalDto,
    RequestPointsWithdrawalUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/referrals", tags=["referrals"])


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


@router.get("/me", response_model=ReferralStatsResponse)
@inject
async def get_my_referral_stats(
    use_case: FromDishka[GetOwnReferralStatsUseCase],
    actor: UserDto = Depends(get_current_actor),
) -> ReferralStatsResponse:
    return _stats_to_response(await use_case(actor))


@router.post("/attach", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def attach_referral(
    payload: AttachReferralRequest,
    use_case: FromDishka[AttachReferralUseCase],
    actor: UserDto = Depends(get_current_actor),
) -> None:
    try:
        await use_case(actor, AttachReferralDto(code=payload.code))
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/withdraw", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def withdraw_points(
    payload: WithdrawPointsRequest,
    use_case: FromDishka[RequestPointsWithdrawalUseCase],
    actor: UserDto = Depends(get_current_actor),
) -> None:
    try:
        await use_case(actor, RequestPointsWithdrawalDto(amount=payload.amount))
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
