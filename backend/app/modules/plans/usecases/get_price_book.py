from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import PriceBookDto
from app.modules.plans.price_book import build_price_book
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import PricingRepository


class GetPriceBookUseCase(UseCase[None, PriceBookDto]):
    required_permission = Permission.PRICING_VIEW

    def __init__(
        self,
        plan_repository: PlanRepository,
        addon_repository: AddOnRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._plan_repository = plan_repository
        self._addon_repository = addon_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> PriceBookDto:
        async with self._uow:
            return await build_price_book(
                self._plan_repository, self._addon_repository, self._pricing_repository
            )
