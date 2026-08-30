from app.core.enums import PlanAvailability
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanDto
from app.modules.plans.repository import PlanRepository
from app.modules.users import UserDto


class ListActivePlansUseCase(UseCase[None, list[PlanDto]]):
    required_permission = Permission.PUBLIC

    def __init__(self, plan_repository: PlanRepository) -> None:
        self._plan_repository = plan_repository

    async def _execute(self, actor: UserDto, data: None) -> list[PlanDto]:
        plans = await self._plan_repository.list_active()
        return [plan for plan in plans if self._is_visible(plan, actor)]

    @staticmethod
    def _is_visible(plan: PlanDto, actor: UserDto) -> bool:
        if plan.availability == PlanAvailability.ALL:
            return True
        if plan.availability == PlanAvailability.ALLOWED:
            return (
                actor.telegram_id is not None and actor.telegram_id in plan.allowed_telegram_ids
            ) or (actor.email is not None and actor.email in plan.allowed_emails)
        # NEW/EXISTING/INVITED/LINK need subscription/invite state that doesn't
        # exist yet (subscriptions is future work per CLAUDE.md) -- hide until it lands.
        return False
