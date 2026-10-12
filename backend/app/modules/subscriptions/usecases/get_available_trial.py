from app.core.db.uow import UnitOfWork
from app.core.enums import PlanAvailability
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import PlanRepository
from app.modules.subscriptions.dto import GetAvailableTrialDto
from app.modules.subscriptions.eligibility import PurchaseEligibility
from app.modules.users import UserDto


class GetAvailableTrialUseCase(UseCase[None, GetAvailableTrialDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        plan_repository: PlanRepository,
        eligibility: PurchaseEligibility,
        uow: UnitOfWork,
    ) -> None:
        self._plan_repository = plan_repository
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
                if plan.free_trial_duration() is not None
                and plan.availability != PlanAvailability.LINK
            ]
            eligible = next(iter(await self._eligibility.purchasable(trial_plans, actor)), None)
            return GetAvailableTrialDto(plan=eligible, is_trial_available=True)
