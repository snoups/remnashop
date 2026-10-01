from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from app.api.dependencies.public import get_current_user
from app.api.dependencies.rate_limit import user_rate_limit
from app.api.errors import error_responses
from app.core.constants import TIME_1H
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
    actor: UserDto = Depends(get_current_user),
) -> ReferralStatsResponse:
    return _stats_to_response(await use_case(actor))


@router.post(
    "/actions/attach", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(400)
)
@inject
async def attach_referral(
    payload: AttachReferralRequest,
    use_case: FromDishka[AttachReferralUseCase],
    actor: UserDto = Depends(get_current_user),
) -> None:
    await use_case(actor, AttachReferralDto(code=payload.code))


@router.post(
    "/actions/withdraw",
    status_code=status.HTTP_204_NO_CONTENT,
    # each request is an audit-log row an admin works through by hand
    dependencies=[Depends(user_rate_limit(key="points_withdraw", limit=5, window_seconds=TIME_1H))],
    responses=error_responses(400),
)
@inject
async def withdraw_points(
    payload: WithdrawPointsRequest,
    use_case: FromDishka[RequestPointsWithdrawalUseCase],
    actor: UserDto = Depends(get_current_user),
) -> None:
    await use_case(actor, RequestPointsWithdrawalDto(amount=payload.amount))
