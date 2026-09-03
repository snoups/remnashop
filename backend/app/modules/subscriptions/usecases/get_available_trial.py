from dataclasses import dataclass
from typing import Optional

from app.core.enums import PlanAvailability
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import PlanDto, PlanRepository, is_plan_purchasable_by
from app.modules.referrals import ReferralRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class GetAvailableTrialResult:
    plan: Optional[PlanDto]
    is_trial_available: bool


class GetAvailableTrialUseCase(UseCase[None, GetAvailableTrialResult]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        plan_repository: PlanRepository,
        subscription_repository: SubscriptionRepository,
        referral_repository: ReferralRepository,
    ) -> None:
        self._plan_repository = plan_repository
        self._subscription_repository = subscription_repository
        self._referral_repository = referral_repository

    async def _execute(self, actor: UserDto, data: None) -> GetAvailableTrialResult:
        if not actor.is_trial_available:
            return GetAvailableTrialResult(plan=None, is_trial_available=False)

        plans = await self._plan_repository.list_active()
        trial_plans = [
            plan for plan in plans if plan.is_trial and plan.availability != PlanAvailability.LINK
        ]
        if not trial_plans:
            return GetAvailableTrialResult(plan=None, is_trial_available=True)

        has_purchase_history = await self._subscription_repository.has_any_subscription(
            actor.id, include_trial=False
        )
        has_referrer = await self._referral_repository.has_referrer(actor.id)
        eligible = next(
            (
                plan
                for plan in trial_plans
                if is_plan_purchasable_by(
                    plan,
                    actor,
                    has_purchase_history=has_purchase_history,
                    has_referrer=has_referrer,
                )
            ),
            None,
        )
        return GetAvailableTrialResult(plan=eligible, is_trial_available=True)
