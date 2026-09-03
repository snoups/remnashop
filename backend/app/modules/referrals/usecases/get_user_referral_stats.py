from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.dto import ReferralStatsDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserDto, UserRepository


class GetUserReferralStatsUseCase(UseCase[int, ReferralStatsDto]):
    required_permission = Permission.REFERRALS_VIEW

    def __init__(
        self, referral_repository: ReferralRepository, user_repository: UserRepository
    ) -> None:
        self._referral_repository = referral_repository
        self._user_repository = user_repository

    async def _execute(self, actor: UserDto, data: int) -> ReferralStatsDto:
        target = await self._user_repository.get_by_id(data)
        if target is None:
            raise NotFoundError(f"User '{data}' not found")

        edge = await self._referral_repository.get_by_referred_id(target.id)
        counts = await self._referral_repository.count_by_level(target.id)
        rewards = await self._referral_repository.list_rewards_by_referrer(target.id)
        return ReferralStatsDto(
            referral_code=target.referral_code,
            referrer_id=edge.referrer_id if edge is not None else None,
            points=target.points,
            counts_by_level=counts,
            rewards=rewards,
        )
