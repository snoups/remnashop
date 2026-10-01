from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.dto import ReferralStatsDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserRepository


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
            target = await self._user_repository.get_by_id(data)
            if target is None:
                raise NotFoundError(f"User '{data}' not found", code=ErrorCode.USER_NOT_FOUND)

            edge = await self._referral_repository.get_by_referred_id(target.id)
            counts = await self._referral_repository.count_by_level(target.id)
            rewards = await self._referral_repository.list_rewards_by_referrer(target.id)
            buyer_ids = list({r.buyer_id for r in rewards if r.buyer_id is not None})
            buyer_levels = await self._referral_repository.downline_depths(target.id, buyer_ids)
            referrer_id = edge.referrer_id if edge is not None else None
            user_ids = buyer_ids + ([referrer_id] if referrer_id is not None else [])
            users = await self._user_repository.list_by_ids(user_ids)
            return ReferralStatsDto(
                referral_code=target.referral_code,
                referrer_id=referrer_id,
                points=target.points,
                counts_by_level=counts,
                rewards=rewards,
                users={user.id: user for user in users},
                buyer_levels=buyer_levels,
            )
