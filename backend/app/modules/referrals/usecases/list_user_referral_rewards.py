from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.referrals.dto import ListUserReferralRewardsDto, ReferralStatsRewardDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserRepository, get_visible_target, visible_user


class ListUserReferralRewardsUseCase(
    UseCase[ListUserReferralRewardsDto, tuple[list[ReferralStatsRewardDto], int]]
):
    required_permission = Permission.REFERRALS_VIEW

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
        self, actor: Actor, data: ListUserReferralRewardsDto
    ) -> tuple[list[ReferralStatsRewardDto], int]:
        async with self._uow:
            await get_visible_target(self._user_repository, actor, data.user_id)
            sees_staff = PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE)
            rewards, total = await self._referral_repository.list_rewards_by_referrer_page(
                data.user_id,
                hide_staff_from=None if sees_staff else actor.id,
                page=data.page,
                page_size=data.page_size,
            )
            buyer_ids = list({r.buyer_id for r in rewards if r.buyer_id is not None})
            levels = await self._referral_repository.downline_depths(data.user_id, buyer_ids)
            users = {user.id: user for user in await self._user_repository.list_by_ids(buyer_ids)}
        items = [
            ReferralStatsRewardDto(
                type=r.type,
                amount=r.amount,
                created_at=r.created_at,
                buyer=visible_user(actor, users.get(r.buyer_id))
                if r.buyer_id is not None
                else None,
                level=levels.get(r.buyer_id) if r.buyer_id is not None else None,
            )
            for r in rewards
        ]
        return items, total
