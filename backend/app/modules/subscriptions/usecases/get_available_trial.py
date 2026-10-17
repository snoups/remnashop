from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import PlanRepository
from app.modules.pricing import PricingRepository
from app.modules.subscriptions.dto import GetAvailableTrialDto
from app.modules.subscriptions.eligibility import PurchaseEligibility
from app.modules.subscriptions.trials import pick_trial
from app.modules.users import UserDto


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
            return await pick_trial(
                self._plan_repository, self._pricing_repository, self._eligibility, actor
            )
