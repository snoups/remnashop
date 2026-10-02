from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.dto import ReferralStatsDto, ReferralStatsRewardDto
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
            users = {user.id: user for user in await self._user_repository.list_by_ids(user_ids)}
        return ReferralStatsDto(
            referral_code=target.referral_code,
            referrer_id=referrer_id,
            points=target.points,
            counts_by_level=counts,
            rewards=[
                ReferralStatsRewardDto(
                    type=r.type,
                    amount=r.amount,
                    created_at=r.created_at,
                    buyer=users.get(r.buyer_id) if r.buyer_id is not None else None,
                    level=buyer_levels.get(r.buyer_id) if r.buyer_id is not None else None,
                )
                for r in rewards
            ],
            referrer=users.get(referrer_id) if referrer_id is not None else None,
        )
