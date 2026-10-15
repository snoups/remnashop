from decimal import Decimal

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.pricing import PricingRepository
from app.modules.referrals.dto import ReferralRevenueDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.transactions import TransactionRepository
from app.modules.users import UserRepository, get_visible_target


class GetUserReferralRevenueUseCase(UseCase[int, ReferralRevenueDto]):
    required_permission = Permission.REFERRALS_REVENUE_VIEW

    def __init__(
        self,
        referral_repository: ReferralRepository,
        user_repository: UserRepository,
        transaction_repository: TransactionRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._referral_repository = referral_repository
        self._user_repository = user_repository
        self._transaction_repository = transaction_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> ReferralRevenueDto:
        async with self._uow:
            await get_visible_target(self._user_repository, actor, data)
            sees_staff = PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE)
            downline = await self._referral_repository.downline_user_ids(
                data, hide_staff_from=None if sees_staff else actor.id
            )
            paid = await self._transaction_repository.sum_paid_anchor_amount_per_user(downline)
            rate_table = await self._pricing_repository.get_rate_table()
        amount = sum(paid.values(), start=Decimal(0))
        return ReferralRevenueDto(amount=amount, currency=rate_table.anchor, paying_count=len(paid))
