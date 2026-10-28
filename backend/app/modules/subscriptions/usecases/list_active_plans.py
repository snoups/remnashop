import hmac
from typing import Optional

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PlanAvailability
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import PlanDto, PlanRepository
from app.modules.pricing import CurrencyRateTable, PricingRepository, price_for
from app.modules.subscriptions.dto import (
    CatalogDurationDto,
    CatalogPlanDto,
    CatalogPriceDto,
    ListActivePlansDto,
    PlanCatalogDto,
)
from app.modules.subscriptions.eligibility import PurchaseEligibility
from app.modules.users import UserDto


def _to_catalog_plan(plan: PlanDto, rates: CurrencyRateTable) -> CatalogPlanDto:
    return CatalogPlanDto(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        tag=plan.tag,
        type=plan.type,
        traffic_limit_strategy=plan.traffic_limit_strategy,
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        is_trial=plan.is_trial,
        order_index=plan.order_index,
        durations=[
            CatalogDurationDto(
                days=duration.days,
                order_index=duration.order_index,
                prices=[
                    CatalogPriceDto(
                        currency=currency,
                        price=price_for(duration.base_price, duration.overrides, currency, rates),
                    )
                    for currency in Currency
                ],
            )
            for duration in plan.sellable_durations()
        ],
    )


class ListActivePlansUseCase(UseCase[ListActivePlansDto, PlanCatalogDto, UserDto]):
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

    async def _execute(self, actor: UserDto, data: Optional[ListActivePlansDto]) -> PlanCatalogDto:
        code = data.plan_code if data is not None else None
        renew_id = data.renew_subscription_id if data is not None else None
        async with self._uow:
            plans = await self._plan_repository.list_active()
            if renew_id is not None:
                try:
                    purchasable = await self._eligibility.renewable(plans, actor.id, renew_id)
                except ValidationError:
                    # someone else's subscription: nothing to renew
                    purchasable = []
            elif code is None:
                # LINK plans are reachable only by code or link, a trial only by
                # the trial button (GetAvailableTrialUseCase picks the one to offer)
                purchasable = await self._eligibility.purchasable(
                    [
                        plan
                        for plan in plans
                        if plan.availability != PlanAvailability.LINK and not plan.is_trial
                    ],
                    actor,
                )
            else:
                purchasable = await self._eligibility.purchasable(
                    [
                        plan
                        for plan in plans
                        if hmac.compare_digest(plan.public_code.encode(), code.encode())
                    ],
                    actor,
                )
            rates = await self._pricing_repository.get_rate_table()
        return PlanCatalogDto(
            plans=[
                _to_catalog_plan(plan, rates) for plan in purchasable if plan.sellable_durations()
            ],
            anchor_currency=rates.anchor,
        )
