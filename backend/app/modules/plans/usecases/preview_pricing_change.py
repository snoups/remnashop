from decimal import Decimal
from typing import Optional

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import (
    AddOnDto,
    BasePriceAdjustmentDto,
    PlanDto,
    PricingChangePreviewDto,
    PricingDiffDto,
    PricingDiffRow,
    ScaledAmountDto,
)
from app.modules.plans.ports import AnchorAmountRescaler, LoyaltyThresholdRescaler
from app.modules.plans.price_projection import (
    adjusted_base_prices,
    anchor_switch,
    scale_unit_price,
)
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import (
    NON_ANCHOR_CURRENCIES,
    CurrencyRateTable,
    PricingRepository,
    resolve_price,
)


class PreviewPricingChangeUseCase(UseCase[PricingChangePreviewDto, PricingDiffDto]):
    required_permission = Permission.PRICING_PREVIEW_VIEW

    def __init__(
        self,
        plan_repository: PlanRepository,
        addon_repository: AddOnRepository,
        pricing_repository: PricingRepository,
        anchor_amount_rescaler: AnchorAmountRescaler,
        loyalty_threshold_rescaler: LoyaltyThresholdRescaler,
        uow: UnitOfWork,
    ) -> None:
        self._plan_repository = plan_repository
        self._addon_repository = addon_repository
        self._pricing_repository = pricing_repository
        self._anchor_amount_rescaler = anchor_amount_rescaler
        self._loyalty_threshold_rescaler = loyalty_threshold_rescaler
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

            projected_table, adjustment = self._project(table, plans, addons, data)

            changes: list[PricingDiffRow] = []
            for plan in plans:
                for duration in plan.durations:
                    changes += self._diff_row(
                        name=plan.name,
                        days=duration.days,
                        old_base=duration.base_price,
                        new_base=adjustment.plan_prices.get(duration.id, duration.base_price),
                        old_overrides={o.currency: o.price for o in duration.overrides},
                        new_overrides=adjustment.plan_overrides.get(duration.id),
                        old_table=table,
                        new_table=projected_table,
                    )
            for addon in addons:
                changes += self._diff_row(
                    name=addon.name,
                    old_base=addon.base_price,
                    new_base=adjustment.addon_prices.get(addon.id, addon.base_price),
                    old_overrides={o.currency: o.price for o in addon.overrides},
                    new_overrides=adjustment.addon_overrides.get(addon.id),
                    old_table=table,
                    new_table=projected_table,
                )

            diff = PricingDiffDto(changes=changes, affected_count=len(changes))
            if data.anchor is None:
                return diff
            return await self._with_anchor_side_effects(diff, table.rows[data.anchor].rate)

    async def _with_anchor_side_effects(
        self, diff: PricingDiffDto, factor: Decimal
    ) -> PricingDiffDto:
        settings = await self._pricing_repository.get_settings()
        return diff.model_copy(
            update={
                "price_per_day": self._scaled(settings.price_per_day, factor),
                "price_per_gb": self._scaled(settings.price_per_gb, factor),
                "loyalty_thresholds": (
                    await self._loyalty_threshold_rescaler.preview_rescaled_thresholds(factor)
                ),
                "rescaled_transactions": await self._anchor_amount_rescaler.count_anchor_amounts(),
            }
        )

    def _scaled(self, price: Optional[Decimal], factor: Decimal) -> Optional[ScaledAmountDto]:
        new = scale_unit_price(price, factor)
        if price is None or new is None:
            return None
        return ScaledAmountDto(old=price, new=new)

    def _diff_row(
        self,
        *,
        name: str,
        days: Optional[int] = None,
        old_base: Decimal,
        new_base: Decimal,
        old_overrides: dict[Currency, Decimal],
        # None = the pins stay as they are
        new_overrides: Optional[dict[Currency, Decimal]],
        old_table: CurrencyRateTable,
        new_table: CurrencyRateTable,
    ) -> list[PricingDiffRow]:
        pins = old_overrides if new_overrides is None else new_overrides
        rows = []
        for currency in Currency:
            old_amount = resolve_price(old_base, currency, old_overrides.get(currency), old_table)
            new_amount = resolve_price(new_base, currency, pins.get(currency), new_table)
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
    ) -> tuple[CurrencyRateTable, BasePriceAdjustmentDto]:
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
            return CurrencyRateTable(anchor=table.anchor, rows=rows), BasePriceAdjustmentDto()

        if data.anchor is not None:
            switch = anchor_switch(table, data.anchor, plans, addons)
            rows = {
                currency: row.model_copy(update={"rate": switch.rates[currency]})
                for currency, row in table.rows.items()
            }
            return CurrencyRateTable(anchor=data.anchor, rows=rows), BasePriceAdjustmentDto(
                plan_prices=switch.plan_base_prices, addon_prices=switch.addon_base_prices
            )

        assert data.adjust is not None
        return table, adjusted_base_prices(data.adjust, plans, addons, table)
