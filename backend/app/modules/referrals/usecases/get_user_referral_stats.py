from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.referrals.dto import UserReferralStatsDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserRepository, get_visible_target, visible_user


class GetUserReferralStatsUseCase(UseCase[int, UserReferralStatsDto]):
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

    async def _execute(self, actor: Actor, data: int) -> UserReferralStatsDto:
        async with self._uow:
            target = await get_visible_target(self._user_repository, actor, data)

            edge = await self._referral_repository.find_by_referred_id(target.id)
            sees_staff = PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE)
            hide_staff_from = None if sees_staff else actor.id
            counts = await self._referral_repository.count_by_level(
                target.id, hide_staff_from=hide_staff_from
            )
            rewards = await self._referral_repository.reward_totals_by_referrer(
                target.id, hide_staff_from=hide_staff_from
            )
            referrer_id = edge.referrer_id if edge is not None else None
            referrer = (
                await self._user_repository.find_by_id(referrer_id)
                if referrer_id is not None
                else None
            )
        return UserReferralStatsDto(
            referral_code=target.referral_code,
            referrer_id=referrer_id,
            points=target.points,
            bonus_days=target.bonus_days,
            counts_by_level=counts,
            rewards=rewards,
            referrer=visible_user(actor, referrer),
        )
