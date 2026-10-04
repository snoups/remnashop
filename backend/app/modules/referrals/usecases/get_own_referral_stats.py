from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.dto import ReferralStatsDto, ReferralStatsRewardDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserDto


class GetOwnReferralStatsUseCase(UseCase[None, ReferralStatsDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(self, referral_repository: ReferralRepository, uow: UnitOfWork) -> None:
        self._referral_repository = referral_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> ReferralStatsDto:
        async with self._uow:
            edge = await self._referral_repository.get_by_referred_id(actor.id)
            counts = await self._referral_repository.count_by_level(actor.id)
            rewards = await self._referral_repository.list_rewards_by_referrer(actor.id)
            return ReferralStatsDto(
                referral_code=actor.referral_code,
                referrer_id=edge.referrer_id if edge is not None else None,
                points=actor.points,
                bonus_days=actor.bonus_days,
                counts_by_level=counts,
                rewards=[
                    ReferralStatsRewardDto(type=r.type, amount=r.amount, created_at=r.created_at)
                    for r in rewards
                ],
            )
