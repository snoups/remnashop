from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.dto import (
    ReferralProgramDto,
    ReferralStatsDto,
    ReferralStatsRewardDto,
)
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserDto, UserRepository, visible_user


class GetOwnReferralStatsUseCase(UseCase[None, ReferralStatsDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        referral_repository: ReferralRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._referral_repository = referral_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> ReferralStatsDto:
        async with self._uow:
            edge = await self._referral_repository.find_by_referred_id(actor.id)
            counts = await self._referral_repository.count_by_level(actor.id)
            rewards = await self._referral_repository.list_rewards_by_referrer(actor.id)
            settings = await self._referral_repository.get_settings()
            # a staff referrer stays hidden from the customer, as elsewhere
            referrer = (
                visible_user(actor, await self._user_repository.find_by_id(edge.referrer_id))
                if edge is not None and edge.referrer_id is not None
                else None
            )
            return ReferralStatsDto(
                referral_code=actor.referral_code,
                referrer_id=referrer.id if referrer is not None else None,
                points=actor.points,
                bonus_days=actor.bonus_days,
                counts_by_level=counts,
                rewards=[
                    ReferralStatsRewardDto(type=r.type, amount=r.amount, created_at=r.created_at)
                    for r in rewards
                ],
                program=ReferralProgramDto(
                    enabled=settings.enabled,
                    reward_type=settings.reward_type,
                    reward_strategy=settings.reward_strategy,
                    reward_amounts=settings.reward_amounts,
                    invitee_reward_type=settings.invitee_reward_type,
                    invitee_reward_amount=settings.invitee_reward_amount,
                ),
            )
