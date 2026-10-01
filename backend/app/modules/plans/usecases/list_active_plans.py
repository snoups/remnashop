from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PlanAvailability
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.access import is_plan_purchasable_by
from app.modules.plans.dto import PlanDto
from app.modules.plans.repository import PlanRepository
from app.modules.referrals import ReferralRepository
from app.modules.subscriptions import SubscriptionRepository


class ListActivePlansUseCase(UseCase[None, list[PlanDto]]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        plan_repository: PlanRepository,
        subscription_repository: SubscriptionRepository,
        referral_repository: ReferralRepository,
        uow: UnitOfWork,
    ) -> None:
        self._plan_repository = plan_repository
        self._subscription_repository = subscription_repository
        self._referral_repository = referral_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> list[PlanDto]:
        async with self._uow:
            plans = await self._plan_repository.list_active()
            # LINK plans are never listed in the catalog -- only reachable by
            # direct code/link, matching main's GetAvailablePlans (no case for LINK).
            plans = [plan for plan in plans if plan.availability != PlanAvailability.LINK]
            has_purchase_history = await self._subscription_repository.has_any_subscription(
                actor.id, include_trial=False
            )
            has_referrer = await self._referral_repository.has_referrer(actor.id)
            return [
                plan
                for plan in plans
                if is_plan_purchasable_by(
                    plan,
                    actor,
                    has_purchase_history=has_purchase_history,
                    has_referrer=has_referrer,
                )
            ]
