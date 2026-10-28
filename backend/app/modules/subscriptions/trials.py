from typing import Final

from app.core.enums import Currency, PlanAvailability
from app.modules.plans import PlanDto, PlanRepository
from app.modules.pricing import PricingRepository, price_for
from app.modules.subscriptions.dto import CatalogPriceDto, GetAvailableTrialDto
from app.modules.subscriptions.eligibility import PurchaseEligibility
from app.modules.users import UserDto

# the most targeted trial wins: one granted by name beats one open to everyone
_TRIAL_PRIORITY: Final[dict[PlanAvailability, int]] = {
    PlanAvailability.ALLOWED: 4,
    PlanAvailability.INVITED: 3,
    PlanAvailability.NEW: 2,
    PlanAvailability.ALL: 1,
}


def _priority(plan: PlanDto) -> int:
    return _TRIAL_PRIORITY.get(plan.availability, 0)


async def pick_trial(
    plan_repository: PlanRepository,
    pricing_repository: PricingRepository,
    eligibility: PurchaseEligibility,
    user: UserDto,
) -> GetAvailableTrialDto:
    """The one trial the trial button offers this user, priced in the anchor
    currency. Reads only; callers run it in their own unit of work."""
    if not user.is_trial_available:
        return GetAvailableTrialDto(plan=None, is_trial_available=False)
    trial_plans = [
        plan
        for plan in await plan_repository.list_active()
        if plan.is_trial
        and plan.sellable_durations()
        and plan.availability != PlanAvailability.LINK
    ]
    eligible = await eligibility.purchasable(trial_plans, user)
    if not eligible:
        return GetAvailableTrialDto(plan=None, is_trial_available=True)
    # stable sort: within one priority the catalog order decides
    plan = sorted(eligible, key=_priority, reverse=True)[0]
    duration = plan.sellable_durations()[0]
    rates = await pricing_repository.get_rate_table()
    return GetAvailableTrialDto(
        plan=plan,
        is_trial_available=True,
        price=price_for(duration.base_price, duration.overrides, rates.anchor, rates),
        currency=rates.anchor,
        prices=tuple(
            CatalogPriceDto(
                currency=currency,
                price=price_for(duration.base_price, duration.overrides, currency, rates),
            )
            for currency in Currency
        ),
    )
