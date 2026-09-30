from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.core.db.uow import UnitOfWork
from app.core.enums import ReferralRewardType
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.dto import (
    DEFAULT_PAGE_SIZE,
    ReferralListItemDto,
    ReferralRewardTotalsDto,
)
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserDto, UserRepository


@dataclass(frozen=True, kw_only=True)
class ListReferralsInput:
    level: Optional[int] = None
    created_from: Optional[datetime] = None
    search: Optional[str] = None
    has_rewards: Optional[bool] = None
    reward_type: Optional[ReferralRewardType] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


class ListReferralsUseCase(UseCase[ListReferralsInput, tuple[list[ReferralListItemDto], int]]):
    required_permission = Permission.REFERRALS_LIST

    def __init__(
        self,
        referral_repository: ReferralRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._referral_repository = referral_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(
        self, actor: UserDto, data: ListReferralsInput
    ) -> tuple[list[ReferralListItemDto], int]:
        async with self._uow:
            referrals, total = await self._referral_repository.list_paginated(
                level=data.level,
                created_from=data.created_from,
                search=data.search,
                has_rewards=data.has_rewards,
                reward_type=data.reward_type,
                page=data.page,
                page_size=data.page_size,
            )
            user_ids = {r.referred_id for r in referrals} | {
                r.referrer_id for r in referrals if r.referrer_id is not None
            }
            users = await self._user_repository.list_by_ids(list(user_ids))
            rewards = await self._referral_repository.reward_totals_by_referral(
                [r.id for r in referrals]
            )
        users_by_id = {user.id: user for user in users}
        no_rewards = ReferralRewardTotalsDto(count=0, amounts={})
        items = [
            ReferralListItemDto(
                referral=referral,
                referred=users_by_id.get(referral.referred_id),
                referrer=users_by_id.get(referral.referrer_id)
                if referral.referrer_id is not None
                else None,
                rewards=rewards.get(referral.id, no_rewards),
            )
            for referral in referrals
        ]
        return items, total
