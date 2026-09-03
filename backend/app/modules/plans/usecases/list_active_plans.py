from app.core.enums import PlanAvailability
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.access import is_plan_purchasable_by
from app.modules.plans.dto import PlanDto
from app.modules.plans.repository import PlanRepository
from app.modules.subscriptions import SubscriptionRepository
from app.modules.users import UserDto


class ListActivePlansUseCase(UseCase[None, list[PlanDto]]):
    required_permission = Permission.PUBLIC

    def __init__(
        self, plan_repository: PlanRepository, subscription_repository: SubscriptionRepository
    ) -> None:
        self._plan_repository = plan_repository
        self._subscription_repository = subscription_repository

    async def _execute(self, actor: UserDto, data: None) -> list[PlanDto]:
        plans = await self._plan_repository.list_active()
        # LINK plans are never listed in the catalog -- only reachable by
        # direct code/link, matching main's GetAvailablePlans (no case for LINK).
        plans = [plan for plan in plans if plan.availability != PlanAvailability.LINK]
        has_purchase_history = await self._subscription_repository.has_any_subscription(
            actor.id, include_trial=False
        )
        return [
            plan
            for plan in plans
            if is_plan_purchasable_by(plan, actor, has_purchase_history=has_purchase_history)
        ]
