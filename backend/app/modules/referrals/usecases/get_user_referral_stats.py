from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.referrals.dto import ReferralStatsDto, ReferralStatsRewardDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.referrals.usecases.target import get_visible_target
from app.modules.users import UserRepository, visible_user


class GetUserReferralStatsUseCase(UseCase[int, ReferralStatsDto]):
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

    async def _execute(self, actor: Actor, data: int) -> ReferralStatsDto:
        async with self._uow:
            target = await get_visible_target(self._user_repository, actor, data)

            edge = await self._referral_repository.get_by_referred_id(target.id)
            sees_staff = PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE)
            counts = await self._referral_repository.count_by_level(
                target.id, hide_staff_from=None if sees_staff else actor.id
            )
            rewards = await self._referral_repository.list_rewards_by_referrer(target.id)
            buyer_ids = list({r.buyer_id for r in rewards if r.buyer_id is not None})
            buyer_levels = await self._referral_repository.downline_depths(target.id, buyer_ids)
            referrer_id = edge.referrer_id if edge is not None else None
            user_ids = buyer_ids + ([referrer_id] if referrer_id is not None else [])
            users = {user.id: user for user in await self._user_repository.list_by_ids(user_ids)}
        # rewards for a hidden staff buyer leave with that buyer, as in the invited list
        rewards = [
            r
            for r in rewards
            if r.buyer_id is None
            or r.buyer_id not in users
            or visible_user(actor, users[r.buyer_id]) is not None
        ]
        return ReferralStatsDto(
            referral_code=target.referral_code,
            referrer_id=referrer_id,
            points=target.points,
            bonus_days=target.bonus_days,
            counts_by_level=counts,
            rewards=[
                ReferralStatsRewardDto(
                    type=r.type,
                    amount=r.amount,
                    created_at=r.created_at,
                    buyer=visible_user(actor, users.get(r.buyer_id))
                    if r.buyer_id is not None
                    else None,
                    level=buyer_levels.get(r.buyer_id) if r.buyer_id is not None else None,
                )
                for r in rewards
            ],
            referrer=visible_user(actor, users.get(referrer_id))
            if referrer_id is not None
            else None,
        )
