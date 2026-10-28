from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.public import get_current_user
from app.api.dependencies.rate_limit import user_rate_limit
from app.api.errors import error_responses
from app.core.constants import (
    DEFAULT_PAGE_SIZE,
    POINTS_WITHDRAW_RATE_KEY,
    POINTS_WITHDRAW_RATE_LIMIT,
    TIME_1H,
)
from app.modules.referrals.api.schemas import (
    OwnInvitedUserPageResponse,
    OwnInvitedUserResponse,
    OwnReferralStatsResponse,
    RedeemBonusDaysRequest,
    RedeemBonusDaysResponse,
    WithdrawPointsRequest,
)
from app.modules.referrals.dto import (
    ListOwnInvitedUsersDto,
    RedeemBonusDaysDto,
    RequestPointsWithdrawalDto,
)
from app.modules.referrals.usecases import (
    GetOwnReferralStatsUseCase,
    ListOwnInvitedUsersUseCase,
    RedeemBonusDaysUseCase,
    RequestPointsWithdrawalUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.get("/me", response_model=OwnReferralStatsResponse)
@inject
async def get_my_referral_stats(
    use_case: FromDishka[GetOwnReferralStatsUseCase],
    actor: UserDto = Depends(get_current_user),
) -> OwnReferralStatsResponse:
    return OwnReferralStatsResponse.model_validate(await use_case(actor), from_attributes=True)


@router.get("/me/invited", response_model=OwnInvitedUserPageResponse)
@inject
async def list_my_invited_users(
    use_case: FromDishka[ListOwnInvitedUsersUseCase],
    actor: UserDto = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
) -> OwnInvitedUserPageResponse:
    items, total = await use_case(actor, ListOwnInvitedUsersDto(page=page, page_size=page_size))
    return OwnInvitedUserPageResponse(
        items=[OwnInvitedUserResponse.model_validate(item, from_attributes=True) for item in items],
        total=total,
    )


@router.post(
    "/me/actions/withdraw",
    status_code=status.HTTP_204_NO_CONTENT,
    # each request is an audit-log row an admin works through by hand
    dependencies=[
        Depends(
            user_rate_limit(
                key=POINTS_WITHDRAW_RATE_KEY,
                limit=POINTS_WITHDRAW_RATE_LIMIT,
                window_seconds=TIME_1H,
            )
        )
    ],
    responses=error_responses(400, 404),
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
