from typing import Final

from app.core.db.uow import UnitOfWork
from app.core.enums import PlanAvailability
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import PlanDto, PlanRepository
from app.modules.pricing import PricingRepository, price_for
from app.modules.subscriptions.dto import GetAvailableTrialDto
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


class GetAvailableTrialUseCase(UseCase[None, GetAvailableTrialDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        plan_repository: PlanRepository,
        pricing_repository: PricingRepository,
        eligibility: PurchaseEligibility,
        uow: UnitOfWork,
    ) -> None:
        self._plan_repository = plan_repository
        self._pricing_repository = pricing_repository
        self._eligibility = eligibility
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> GetAvailableTrialDto:
        async with self._uow:
            if not actor.is_trial_available:
                return GetAvailableTrialDto(plan=None, is_trial_available=False)

            plans = await self._plan_repository.list_active()
            trial_plans = [
                plan
                for plan in plans
                if plan.is_trial
                and plan.sellable_durations()
                and plan.availability != PlanAvailability.LINK
            ]
            eligible = await self._eligibility.purchasable(trial_plans, actor)
            if not eligible:
                return GetAvailableTrialDto(plan=None, is_trial_available=True)
            # stable sort: within one priority the catalog order decides
            plan = sorted(eligible, key=_priority, reverse=True)[0]
            duration = plan.sellable_durations()[0]
            rates = await self._pricing_repository.get_rate_table()
        return GetAvailableTrialDto(
            plan=plan,
            is_trial_available=True,
            price=price_for(duration.base_price, duration.overrides, rates.anchor, rates),
            currency=rates.anchor,
        )
