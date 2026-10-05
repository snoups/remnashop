from decimal import Decimal

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.loyalty.dto import UserLoyaltyDto
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.loyalty.tiers import months_before, next_tier
from app.modules.pricing import PricingRepository
from app.modules.transactions import TransactionRepository
from app.modules.users import UserDto, UserRepository


async def build_user_loyalty(
    user: UserDto,
    loyalty_repository: LoyaltyRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
) -> UserLoyaltyDto:
    settings = await loyalty_repository.get_settings()
    paid_since = (
        months_before(datetime_now(), settings.window_months)
        if settings.window_months is not None
        else None
    )
    totals = await transaction_repository.sum_paid_anchor_amount_per_user(
        [user.id], paid_since=paid_since
    )
    spent = totals.get(user.id, Decimal(0))
    pricing = await pricing_repository.get_settings()
    return UserLoyaltyDto(
        user_id=user.id,
        discount=user.loyalty_discount,
        excluded=user.loyalty_excluded,
        spent=spent,
        next_tier=next_tier(spent, settings.tiers),
        currency=pricing.anchor_currency,
    )


class GetUserLoyaltyUseCase(UseCase[int, UserLoyaltyDto]):
    required_permission = Permission.USERS_LOYALTY_VIEW

    def __init__(
        self,
        loyalty_repository: LoyaltyRepository,
        transaction_repository: TransactionRepository,
        user_repository: UserRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._loyalty_repository = loyalty_repository
        self._transaction_repository = transaction_repository
        self._user_repository = user_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> UserLoyaltyDto:
        async with self._uow:
            user = await self._user_repository.get_by_id(data)
            if user is None:
                raise NotFoundError(f"User '{data}' not found", code=ErrorCode.USER_NOT_FOUND)
            return await build_user_loyalty(
                user,
                self._loyalty_repository,
                self._transaction_repository,
                self._pricing_repository,
            )
