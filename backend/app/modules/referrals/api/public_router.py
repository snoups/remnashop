from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from app.api.dependencies.public import get_current_user
from app.api.dependencies.rate_limit import user_rate_limit
from app.api.errors import error_responses
from app.core.constants import TIME_1H
from app.modules.referrals.api.schemas import (
    AttachReferralRequest,
    RedeemBonusDaysRequest,
    RedeemBonusDaysResponse,
    ReferralStatsResponse,
    WithdrawPointsRequest,
)
from app.modules.referrals.dto import (
    AttachReferralDto,
    RedeemBonusDaysDto,
    RequestPointsWithdrawalDto,
)
from app.modules.referrals.usecases.attach_referral import AttachReferralUseCase
from app.modules.referrals.usecases.get_own_referral_stats import GetOwnReferralStatsUseCase
from app.modules.referrals.usecases.redeem_bonus_days import RedeemBonusDaysUseCase
from app.modules.referrals.usecases.request_points_withdrawal import RequestPointsWithdrawalUseCase
from app.modules.users import UserDto

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.get("/me", response_model=ReferralStatsResponse)
@inject
async def get_my_referral_stats(
    use_case: FromDishka[GetOwnReferralStatsUseCase],
    actor: UserDto = Depends(get_current_user),
) -> ReferralStatsResponse:
    return ReferralStatsResponse.model_validate(await use_case(actor), from_attributes=True)


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


@router.post(
    "/me/actions/redeem-days",
    response_model=RedeemBonusDaysResponse,
    responses=error_responses(400),
)
@inject
async def redeem_bonus_days(
    payload: RedeemBonusDaysRequest,
    use_case: FromDishka[RedeemBonusDaysUseCase],
    actor: UserDto = Depends(get_current_user),
) -> RedeemBonusDaysResponse:
    result = await use_case(
        actor, RedeemBonusDaysDto(subscription_id=payload.subscription_id, days=payload.days)
    )
    return RedeemBonusDaysResponse.model_validate(result, from_attributes=True)
