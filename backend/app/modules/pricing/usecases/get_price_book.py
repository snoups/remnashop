from decimal import Decimal

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import PlanRepository
from app.modules.pricing.dto import CurrencyRateTable, PriceBookCell, PriceBookDto, PriceBookRow
from app.modules.pricing.repository import PricingRepository
from app.modules.pricing.resolver import resolve_price
from app.modules.subscriptions import AddOnRepository
from app.modules.users import UserDto


def _build_cells(
    base_price: Decimal, overrides_by_currency: dict[Currency, Decimal], table: CurrencyRateTable
) -> list[PriceBookCell]:
    cells = []
    for currency in Currency:
        override = overrides_by_currency.get(currency)
        amount = resolve_price(base_price, currency, override, table)
        cells.append(
            PriceBookCell(currency=currency, amount=amount, is_pinned=override is not None)
        )
    return cells


async def build_price_book(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
) -> PriceBookDto:
    table = await pricing_repository.get_rate_table()
    settings = await pricing_repository.get_settings()

    plans = await plan_repository.list_all()
    plan_rows = [
        PriceBookRow(
            kind="plan_duration",
            ref_id=duration.id,
            plan_id=plan.id,
            label=f"{plan.name} / {duration.days}d",
            days=duration.days,
            base_price=duration.base_price,
            cells=_build_cells(
                duration.base_price,
                {override.currency: override.price for override in duration.overrides},
                table,
            ),
        )
        for plan in plans
        for duration in plan.durations
    ]

    addons = await addon_repository.list_all()
    addon_rows = [
        PriceBookRow(
            kind="addon",
            ref_id=addon.id,
            label=addon.name,
            days=None,
            base_price=addon.base_price,
            cells=_build_cells(
                addon.base_price,
                {override.currency: override.price for override in addon.overrides},
                table,
            ),
        )
        for addon in addons
    ]

    return PriceBookDto(
        rate_table=list(table.rows.values()),
        settings=settings,
        plans=plan_rows,
        addons=addon_rows,
    )


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

    async def _execute(self, actor: UserDto, data: None) -> PriceBookDto:
        async with self._uow:
            return await build_price_book(
                self._plan_repository, self._addon_repository, self._pricing_repository
            )
