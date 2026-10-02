from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.dto import GetReferralSummaryDto, ReferralSummaryDto
from app.modules.referrals.repository import ReferralRepository


class GetReferralSummaryUseCase(UseCase[GetReferralSummaryDto, ReferralSummaryDto]):
    required_permission = Permission.REFERRALS_SUMMARY_VIEW

    def __init__(self, referral_repository: ReferralRepository, uow: UnitOfWork) -> None:
        self._referral_repository = referral_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: GetReferralSummaryDto) -> ReferralSummaryDto:
        async with self._uow:
            return await self._referral_repository.summarize(
                level=data.level,
                created_from=data.created_from,
                created_to=data.created_to,
                search=data.search,
                has_rewards=data.has_rewards,
                reward_type=data.reward_type,
            )
