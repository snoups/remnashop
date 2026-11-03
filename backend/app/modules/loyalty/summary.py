from app.core.constants import ZERO_AMOUNT
from app.core.utils.time import datetime_now
from app.modules.loyalty.dto import UserLoyaltyDto
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.loyalty.tiers import months_before, next_tier
from app.modules.pricing import PricingRepository
from app.modules.transactions import TransactionRepository
from app.modules.users import UserDto


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
    spent = totals.get(user.id, ZERO_AMOUNT)
    pricing = await pricing_repository.get_settings()
    return UserLoyaltyDto(
        user_id=user.id,
        discount=user.loyalty_discount,
        excluded=user.loyalty_excluded,
        spent=spent,
        next_tier=next_tier(spent, settings.tiers) if settings.enabled else None,
        currency=pricing.anchor_currency,
    )
