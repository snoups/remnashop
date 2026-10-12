from decimal import Decimal
from typing import Optional

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PriceAdjustScope
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import (
    AddOnDto,
    AdjustBasePricesDto,
    PlanDto,
    PlanDurationDto,
    PricingChangePreviewDto,
    PricingDiffDto,
    PricingDiffRow,
)
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import (
    NON_ANCHOR_CURRENCIES,
    RATE_PRECISION,
    CurrencyRateTable,
    PricingRepository,
    resolve_price,
    scale_base_price,
)


class PreviewPricingChangeUseCase(UseCase[PricingChangePreviewDto, PricingDiffDto]):
    required_permission = Permission.PRICING_PREVIEW_VIEW

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

    async def _execute(self, actor: Actor, data: PricingChangePreviewDto) -> PricingDiffDto:
        async with self._uow:
            set_count = sum(x is not None for x in (data.rate, data.anchor, data.adjust))
            if set_count != 1:
                raise ValidationError(
                    "Exactly one of rate/anchor/adjust must be set",
                    code=ErrorCode.PRICING_PREVIEW_AMBIGUOUS,
                )
            if data.anchor in NON_ANCHOR_CURRENCIES:
                raise ValidationError(
                    f"{data.anchor} cannot be the anchor currency",
                    code=ErrorCode.ANCHOR_CURRENCY_INVALID,
                )

            table = await self._pricing_repository.get_rate_table()
            plans = await self._plan_repository.list_all()
            addons = await self._addon_repository.list_all()

            projected_table, plan_base_prices, addon_base_prices = self._project(
                table, plans, addons, data
            )

            changes: list[PricingDiffRow] = []
            for plan in plans:
                for duration in plan.durations:
                    changes += self._diff_row(
                        name=plan.name,
                        days=duration.days,
                        old_base=duration.base_price,
                        new_base=plan_base_prices.get(duration.id, duration.base_price),
                        overrides_by_currency={o.currency: o.price for o in duration.overrides},
                        old_table=table,
                        new_table=projected_table,
                    )
            for addon in addons:
                changes += self._diff_row(
                    name=addon.name,
                    old_base=addon.base_price,
                    new_base=addon_base_prices.get(addon.id, addon.base_price),
                    overrides_by_currency={o.currency: o.price for o in addon.overrides},
                    old_table=table,
                    new_table=projected_table,
                )

            return PricingDiffDto(changes=changes, affected_count=len(changes))

    def _diff_row(
        self,
        *,
        name: str,
        days: Optional[int] = None,
        old_base: Decimal,
        new_base: Decimal,
        overrides_by_currency: dict[Currency, Decimal],
        old_table: CurrencyRateTable,
        new_table: CurrencyRateTable,
    ) -> list[PricingDiffRow]:
        rows = []
        for currency in Currency:
            override = overrides_by_currency.get(currency)
            old_amount = resolve_price(old_base, currency, override, old_table)
            new_amount = resolve_price(new_base, currency, override, new_table)
            if old_amount != new_amount:
                rows.append(
                    PricingDiffRow(
                        name=name, days=days, currency=currency, old=old_amount, new=new_amount
                    )
                )
        return rows

    def _project(
        self,
        table: CurrencyRateTable,
        plans: list[PlanDto],
        addons: list[AddOnDto],
        data: PricingChangePreviewDto,
    ) -> tuple[CurrencyRateTable, dict[int, Decimal], dict[int, Decimal]]:
        if data.rate is not None:
            rows = dict(table.rows)
            rows[data.rate.currency] = rows[data.rate.currency].model_copy(
                update={
                    "rate": data.rate.rate,
                    "rounding_mode": data.rate.rounding_mode,
                    "charm_ending": data.rate.charm_ending,
                    "min_amount": data.rate.min_amount,
                }
            )
            return CurrencyRateTable(anchor=table.anchor, rows=rows), {}, {}

        if data.anchor is not None:
            factor = table.rows[data.anchor].rate
            rows = {
                currency: row.model_copy(
                    update={"rate": (row.rate / factor).quantize(RATE_PRECISION)}
                )
                for currency, row in table.rows.items()
            }
            rows[data.anchor] = rows[data.anchor].model_copy(update={"rate": Decimal("1.000000")})
            projected_table = CurrencyRateTable(anchor=data.anchor, rows=rows)
            plan_base_prices = {
                duration.id: scale_base_price(duration.base_price, factor)
                for plan in plans
                for duration in plan.durations
            }
            addon_base_prices = {
                addon.id: scale_base_price(addon.base_price, factor) for addon in addons
            }
            return projected_table, plan_base_prices, addon_base_prices

        assert data.adjust is not None
        return table, *self._project_adjust(data.adjust, plans, addons)

    def _project_adjust(
        self, adjust: AdjustBasePricesDto, plans: list[PlanDto], addons: list[AddOnDto]
    ) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
        plan_base_prices: dict[int, Decimal] = {}
        addon_base_prices: dict[int, Decimal] = {}

        if adjust.scope in (PriceAdjustScope.ALL_PLANS, PriceAdjustScope.SELECTED):
            durations: list[PlanDurationDto] = [
                duration for plan in plans for duration in plan.durations
            ]
            if adjust.scope is PriceAdjustScope.SELECTED:
                selected_ids = set(adjust.plan_duration_ids)
                durations = [duration for duration in durations if duration.id in selected_ids]
            plan_base_prices = {
                duration.id: scale_base_price(duration.base_price, adjust.factor)
                for duration in durations
            }

        if adjust.scope in (PriceAdjustScope.ALL_ADDONS, PriceAdjustScope.SELECTED):
            targets = addons
            if adjust.scope is PriceAdjustScope.SELECTED:
                selected_ids = set(adjust.addon_ids)
                targets = [addon for addon in targets if addon.id in selected_ids]
            addon_base_prices = {
                addon.id: scale_base_price(addon.base_price, adjust.factor) for addon in targets
            }

        return plan_base_prices, addon_base_prices
