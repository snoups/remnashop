from decimal import Decimal

from app.core.db.uow import UnitOfWork
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.payments import PaymentOrderRepository
from app.modules.pricing import PricingRepository, convert_for_report
from app.modules.referrals.dto import ReferralRevenueDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserDto, UserRepository


class GetUserReferralRevenueUseCase(UseCase[int, ReferralRevenueDto]):
    required_permission = Permission.REFERRALS_REVENUE_VIEW

    def __init__(
        self,
        referral_repository: ReferralRepository,
        user_repository: UserRepository,
        payment_order_repository: PaymentOrderRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._referral_repository = referral_repository
        self._user_repository = user_repository
        self._payment_order_repository = payment_order_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> ReferralRevenueDto:
        async with self._uow:
            if await self._user_repository.get_by_id(data) is None:
                raise NotFoundError(f"User '{data}' not found")
            downline = await self._referral_repository.downline_user_ids(data)
            paid = await self._payment_order_repository.sum_paid_final_price_per_user(downline)
            rate_table = await self._pricing_repository.get_rate_table()
        amount = sum(
            (
                convert_for_report(total, currency, rate_table.anchor, rate_table)
                for by_currency in paid.values()
                for currency, total in by_currency.items()
            ),
            start=Decimal(0),
        )
        return ReferralRevenueDto(amount=amount, currency=rate_table.anchor, paying_count=len(paid))
