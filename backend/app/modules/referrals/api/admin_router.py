from datetime import datetime
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.admin import require_admin
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.referrals.api.schemas import (
    AdjustPointsRequest,
    ReferralListItemResponse,
    ReferralPageResponse,
    ReferralRewardResponse,
    ReferralSettingsResponse,
    ReferralStatsResponse,
    ReferralUserResponse,
    UpdateReferralSettingsRequest,
)
from app.modules.referrals.dto import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    ReferralListItemDto,
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
from app.modules.referrals.usecases.list_referrals import (
    ListReferralsInput,
    ListReferralsUseCase,
)
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


def _user_to_response(user: Optional[UserDto]) -> Optional[ReferralUserResponse]:
    if user is None:
        return None
    return ReferralUserResponse(
        id=user.id, name=user.name, username=user.username, telegram_id=user.telegram_id
    )


def _list_item_to_response(item: ReferralListItemDto) -> ReferralListItemResponse:
    return ReferralListItemResponse(
        id=item.referral.id,
        level=item.referral.level,
        created_at=item.referral.created_at,
        referred=_user_to_response(item.referred),
        referrer=_user_to_response(item.referrer),
        reward_count=item.rewards.count,
        reward_amounts=item.rewards.amounts,
    )


@router.get("/referrals", response_model=ReferralPageResponse)
@inject
async def list_referrals(
    use_case: FromDishka[ListReferralsUseCase],
    actor: UserDto = Depends(require_admin),
    level: Optional[int] = Query(None, ge=1, le=3),
    created_from: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> ReferralPageResponse:
    items, total = await use_case(
        actor,
        ListReferralsInput(level=level, created_from=created_from, page=page, page_size=page_size),
    )
    return ReferralPageResponse(items=[_list_item_to_response(item) for item in items], total=total)


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
