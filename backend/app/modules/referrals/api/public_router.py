from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query

from app.api.dependencies.public import get_current_user
from app.api.errors import error_responses
from app.core.constants import DEFAULT_PAGE_SIZE
from app.modules.referrals.api.schemas import (
    BonusDaysTargetsResponse,
    OwnInvitedUserPageResponse,
    OwnInvitedUserResponse,
    OwnReferralStatsResponse,
    RedeemBonusDaysRequest,
    RedeemBonusDaysResponse,
)
from app.modules.referrals.dto import (
    ListOwnInvitedUsersDto,
    RedeemBonusDaysDto,
)
from app.modules.referrals.usecases import (
    GetOwnReferralStatsUseCase,
    ListBonusDaysTargetsUseCase,
    ListOwnInvitedUsersUseCase,
    RedeemBonusDaysUseCase,
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


# what bonus days can extend, by the redemption's own rule: the cabinet's pick list
@router.get("/me/redeem-targets", response_model=BonusDaysTargetsResponse)
@inject
async def list_my_redeem_targets(
    use_case: FromDishka[ListBonusDaysTargetsUseCase],
    actor: UserDto = Depends(get_current_user),
) -> BonusDaysTargetsResponse:
    return BonusDaysTargetsResponse(subscription_ids=[s.id for s in await use_case(actor)])


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
