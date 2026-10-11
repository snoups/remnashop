from datetime import datetime
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import ReferralRewardType
from app.modules.referrals.api.schemas import (
    AdjustBonusDaysRequest,
    AdjustPointsRequest,
    InvitedUserPageResponse,
    InvitedUserResponse,
    ReferralListItemResponse,
    ReferralPageResponse,
    ReferralRevenueResponse,
    ReferralSettingsResponse,
    ReferralStatsResponse,
    ReferralSummaryResponse,
    UpdateReferralSettingsRequest,
)
from app.modules.referrals.dto import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    AdjustUserBonusDaysDto,
    AdjustUserPointsDto,
    GetReferralSummaryDto,
    ListInvitedUsersDto,
    ListReferralsDto,
    ReferralSettingsDto,
    UpdateReferralSettingsDto,
)
from app.modules.referrals.usecases.adjust_user_bonus_days import AdjustUserBonusDaysUseCase
from app.modules.referrals.usecases.adjust_user_points import AdjustUserPointsUseCase
from app.modules.referrals.usecases.get_referral_settings import GetReferralSettingsUseCase
from app.modules.referrals.usecases.get_referral_summary import GetReferralSummaryUseCase
from app.modules.referrals.usecases.get_user_referral_revenue import GetUserReferralRevenueUseCase
from app.modules.referrals.usecases.get_user_referral_stats import GetUserReferralStatsUseCase
from app.modules.referrals.usecases.list_invited_users import ListInvitedUsersUseCase
from app.modules.referrals.usecases.list_referrals import ListReferralsUseCase
from app.modules.referrals.usecases.reset_referral_code import ResetReferralCodeUseCase
from app.modules.referrals.usecases.reset_referral_settings import ResetReferralSettingsUseCase
from app.modules.referrals.usecases.update_referral_settings import UpdateReferralSettingsUseCase

router = APIRouter(tags=["referrals"])


def _settings_to_response(dto: ReferralSettingsDto) -> ReferralSettingsResponse:
    return ReferralSettingsResponse.model_validate(dto, from_attributes=True)


@router.get("/referrals", response_model=ReferralPageResponse)
@inject
async def list_referrals(
    use_case: FromDishka[ListReferralsUseCase],
    actor: Actor = Depends(require_admin),
    level: Optional[int] = Query(None, ge=1, le=3),
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    search: Optional[str] = None,
    has_rewards: Optional[bool] = None,
    reward_type: Optional[ReferralRewardType] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> ReferralPageResponse:
    items, total = await use_case(
        actor,
        ListReferralsDto(
            level=level,
            created_from=created_from,
            created_to=created_to,
            search=search,
            has_rewards=has_rewards,
            reward_type=reward_type,
            page=page,
            page_size=page_size,
        ),
    )
    return ReferralPageResponse(
        items=[
            ReferralListItemResponse.model_validate(item, from_attributes=True) for item in items
        ],
        total=total,
    )


@router.get("/referrals/summary", response_model=ReferralSummaryResponse)
@inject
async def get_referral_summary(
    use_case: FromDishka[GetReferralSummaryUseCase],
    actor: Actor = Depends(require_admin),
    level: Optional[int] = Query(None, ge=1, le=3),
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    search: Optional[str] = None,
    has_rewards: Optional[bool] = None,
    reward_type: Optional[ReferralRewardType] = None,
) -> ReferralSummaryResponse:
    summary = await use_case(
        actor,
        GetReferralSummaryDto(
            level=level,
            created_from=created_from,
            created_to=created_to,
            search=search,
            has_rewards=has_rewards,
            reward_type=reward_type,
        ),
    )
    return ReferralSummaryResponse.model_validate(summary, from_attributes=True)


@router.get("/referrals/settings", response_model=ReferralSettingsResponse)
@inject
async def get_referral_settings(
    use_case: FromDishka[GetReferralSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> ReferralSettingsResponse:
    return _settings_to_response(await use_case(actor))


@router.patch(
    "/referrals/settings", response_model=ReferralSettingsResponse, responses=error_responses(400)
)
@inject
async def update_referral_settings(
    payload: UpdateReferralSettingsRequest,
    use_case: FromDishka[UpdateReferralSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> ReferralSettingsResponse:
    updated = await use_case(
        actor,
        UpdateReferralSettingsDto(
            enabled=payload.enabled,
            max_level=payload.max_level,
            accrual_strategy=payload.accrual_strategy,
            reward_type=payload.reward_type,
            reward_strategy=payload.reward_strategy,
            reward_amounts=payload.reward_amounts,
            days_require_paid_subscription=payload.days_require_paid_subscription,
            invitee_reward_type=payload.invitee_reward_type,
            invitee_reward_amount=payload.invitee_reward_amount,
        ),
    )
    return _settings_to_response(updated)


@router.post("/referrals/settings/actions/reset", response_model=ReferralSettingsResponse)
@inject
async def reset_referral_settings(
    use_case: FromDishka[ResetReferralSettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> ReferralSettingsResponse:
    return _settings_to_response(await use_case(actor))


@router.get(
    "/users/{user_id:int}/referrals",
    response_model=ReferralStatsResponse,
    responses=error_responses(404),
)
@inject
async def get_user_referral_stats(
    user_id: int,
    use_case: FromDishka[GetUserReferralStatsUseCase],
    actor: Actor = Depends(require_admin),
) -> ReferralStatsResponse:
    stats = await use_case(actor, user_id)
    return ReferralStatsResponse.model_validate(stats, from_attributes=True)


@router.post(
    "/users/{user_id:int}/actions/adjust-points",
    response_model=ReferralStatsResponse,
    responses=error_responses(400, 404),
)
@inject
async def adjust_user_points(
    user_id: int,
    payload: AdjustPointsRequest,
    adjust_use_case: FromDishka[AdjustUserPointsUseCase],
    stats_use_case: FromDishka[GetUserReferralStatsUseCase],
    actor: Actor = Depends(require_admin),
) -> ReferralStatsResponse:
    await adjust_use_case(actor, AdjustUserPointsDto(user_id=user_id, delta=payload.delta))
    stats = await stats_use_case(actor, user_id)
    return ReferralStatsResponse.model_validate(stats, from_attributes=True)


@router.post(
    "/users/{user_id:int}/actions/adjust-bonus-days",
    response_model=ReferralStatsResponse,
    responses=error_responses(400, 404),
)
@inject
async def adjust_user_bonus_days(
    user_id: int,
    payload: AdjustBonusDaysRequest,
    adjust_use_case: FromDishka[AdjustUserBonusDaysUseCase],
    stats_use_case: FromDishka[GetUserReferralStatsUseCase],
    actor: Actor = Depends(require_admin),
) -> ReferralStatsResponse:
    await adjust_use_case(actor, AdjustUserBonusDaysDto(user_id=user_id, delta=payload.delta))
    stats = await stats_use_case(actor, user_id)
    return ReferralStatsResponse.model_validate(stats, from_attributes=True)


@router.get(
    "/users/{user_id:int}/referrals/revenue",
    response_model=ReferralRevenueResponse,
    responses=error_responses(404),
)
@inject
async def get_user_referral_revenue(
    user_id: int,
    use_case: FromDishka[GetUserReferralRevenueUseCase],
    actor: Actor = Depends(require_admin),
) -> ReferralRevenueResponse:
    revenue = await use_case(actor, user_id)
    return ReferralRevenueResponse.model_validate(revenue, from_attributes=True)


@router.get(
    "/users/{user_id:int}/referrals/invited",
    response_model=InvitedUserPageResponse,
    responses=error_responses(404),
)
@inject
async def list_invited_users(
    user_id: int,
    use_case: FromDishka[ListInvitedUsersUseCase],
    actor: Actor = Depends(require_admin),
    level: Optional[int] = Query(None, ge=1, le=3),
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> InvitedUserPageResponse:
    items, total = await use_case(
        actor,
        ListInvitedUsersDto(
            user_id=user_id, level=level, search=search, page=page, page_size=page_size
        ),
    )
    return InvitedUserPageResponse(
        items=[InvitedUserResponse.model_validate(item, from_attributes=True) for item in items],
        total=total,
    )


@router.post(
    "/users/{user_id:int}/referral-code/actions/reset",
    response_model=ReferralStatsResponse,
    responses=error_responses(404),
)
@inject
async def reset_user_referral_code(
    user_id: int,
    reset_use_case: FromDishka[ResetReferralCodeUseCase],
    stats_use_case: FromDishka[GetUserReferralStatsUseCase],
    actor: Actor = Depends(require_admin),
) -> ReferralStatsResponse:
    await reset_use_case(actor, user_id)
    stats = await stats_use_case(actor, user_id)
    return ReferralStatsResponse.model_validate(stats, from_attributes=True)
