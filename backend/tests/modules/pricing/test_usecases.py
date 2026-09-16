from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import AddOnType, Currency, PlanType, PriceAdjustScope, Role, RoundingMode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.modules.plans.dto import (
    CreatePlanDto,
    PlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    SetPlanPriceOverrideDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.pricing.dto import (
    AdjustBasePricesDto,
    PricingChangePreviewDto,
    SwitchAnchorCurrencyDto,
    UpdateCurrencyRateDto,
    UpdatePricingSettingsDto,
)
from app.modules.pricing.repository import PricingRepository
from app.modules.pricing.usecases import (
    AdjustBasePricesUseCase,
    GetPriceBookUseCase,
    PreviewPricingChangeUseCase,
    SwitchAnchorCurrencyUseCase,
    UpdateCurrencyRateUseCase,
    UpdatePricingSettingsUseCase,
)
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import AddOnDto, CreateAddOnDto
from app.modules.users.dto import UserDto

OWNER = UserDto(name="owner", role=Role.OWNER)


async def _seed_catalog(
    plan_repository: PlanRepository, addon_repository: AddOnRepository
) -> tuple[PlanDto, AddOnDto]:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=created.id, internal_squads=[uuid4()], external_squad=None)
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("2.00"))],
        )
    )
    plan = await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))

    addon = await addon_repository.create(
        CreateAddOnDto(
            name="Extra traffic", type=AddOnType.TRAFFIC, amount=10, base_price=Decimal("1.00")
        )
    )
    return plan, addon


async def test_price_book_lists_derived_and_pinned_cells(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
) -> None:
    await pricing_repository.get_rate_table()
    await pricing_repository.update_rate(
        UpdateCurrencyRateDto(
            currency=Currency.RUB,
            rate=Decimal("95"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("10"),
        )
    )
    plan, addon = await _seed_catalog(plan_repository, addon_repository)
    duration_id = plan.durations[0].id
    await plan_repository.set_price_override(
        SetPlanPriceOverrideDto(
            plan_id=plan.id,
            days=30,
            currency=Currency.RUB,
            price=Decimal("250"),
            anchor=Currency.USD,
        )
    )

    book = await GetPriceBookUseCase(plan_repository, addon_repository, pricing_repository, uow)(
        OWNER
    )

    plan_row = next(row for row in book.plans if row.ref_id == duration_id)
    assert plan_row.plan_id == plan.id
    rub_cell = next(c for c in plan_row.cells if c.currency is Currency.RUB)
    assert rub_cell.amount == Decimal("250")
    assert rub_cell.is_pinned is True

    addon_row = next(row for row in book.addons if row.ref_id == addon.id)
    assert addon_row.plan_id is None
    addon_rub_cell = next(c for c in addon_row.cells if c.currency is Currency.RUB)
    assert addon_rub_cell.amount == Decimal("95")  # 1.00 * 95
    assert addon_rub_cell.is_pinned is False


async def test_update_currency_rate_moves_the_book(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await pricing_repository.get_rate_table()
    plan, _ = await _seed_catalog(plan_repository, addon_repository)

    rows = await UpdateCurrencyRateUseCase(pricing_repository, uow, event_publisher)(
        OWNER,
        UpdateCurrencyRateDto(
            currency=Currency.RUB,
            rate=Decimal("100"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("10"),
        ),
    )
    rub_row = next(r for r in rows if r.currency is Currency.RUB)
    assert rub_row.rate == Decimal("100")

    book = await GetPriceBookUseCase(plan_repository, addon_repository, pricing_repository, uow)(
        OWNER
    )
    plan_row = next(row for row in book.plans if row.ref_id == plan.durations[0].id)
    rub_cell = next(c for c in plan_row.cells if c.currency is Currency.RUB)
    assert rub_cell.amount == Decimal("200")  # 2.00 * 100


async def test_switch_anchor_keeps_derived_prices_stable(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await pricing_repository.get_rate_table()
    await pricing_repository.update_rate(
        UpdateCurrencyRateDto(
            currency=Currency.RUB,
            rate=Decimal("95"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("10"),
        )
    )
    plan, _ = await _seed_catalog(plan_repository, addon_repository)
    duration_id = plan.durations[0].id

    before = await GetPriceBookUseCase(plan_repository, addon_repository, pricing_repository, uow)(
        OWNER
    )
    await SwitchAnchorCurrencyUseCase(
        pricing_repository, plan_repository, addon_repository, uow, event_publisher
    )(OWNER, SwitchAnchorCurrencyDto(new_anchor=Currency.RUB))
    after = await GetPriceBookUseCase(plan_repository, addon_repository, pricing_repository, uow)(
        OWNER
    )

    b = next(c for c in before.plans[0].cells if c.currency is Currency.RUB).amount
    a = next(row for row in after.plans if row.ref_id == duration_id)
    a_amount = next(c for c in a.cells if c.currency is Currency.RUB).amount
    assert abs(a_amount - b) <= Decimal("1")
    assert after.settings.anchor_currency is Currency.RUB


async def test_preview_pricing_change_writes_nothing(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
) -> None:
    await pricing_repository.get_rate_table()
    await pricing_repository.update_rate(
        UpdateCurrencyRateDto(
            currency=Currency.RUB,
            rate=Decimal("95"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("10"),
        )
    )
    plan, addon = await _seed_catalog(plan_repository, addon_repository)

    before_plan = await plan_repository.get_by_id(plan.id)
    before_addon = await addon_repository.get_by_id(addon.id)

    diff = await PreviewPricingChangeUseCase(
        plan_repository, addon_repository, pricing_repository, uow
    )(
        OWNER,
        PricingChangePreviewDto(
            rate=UpdateCurrencyRateDto(
                currency=Currency.RUB,
                rate=Decimal("100"),
                rounding_mode=RoundingMode.INTEGER,
                charm_ending=None,
                min_amount=Decimal("10"),
            )
        ),
    )

    assert diff.affected_count > 0
    assert any(row.currency is Currency.RUB for row in diff.changes)

    after_plan = await plan_repository.get_by_id(plan.id)
    after_addon = await addon_repository.get_by_id(addon.id)
    assert after_plan.durations[0].base_price == before_plan.durations[0].base_price
    assert after_addon.base_price == before_addon.base_price

    rate_after = await pricing_repository.get_rate_table()
    assert rate_after.for_currency(Currency.RUB).rate == Decimal("95")


async def test_preview_pricing_change_rejects_ambiguous_request(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
) -> None:
    use_case = PreviewPricingChangeUseCase(
        plan_repository, addon_repository, pricing_repository, uow
    )
    with pytest.raises(ValidationError):
        await use_case(OWNER, PricingChangePreviewDto())


async def test_adjust_base_prices_multiplies_scope_and_leaves_overrides_untouched(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await pricing_repository.get_rate_table()
    plan, addon = await _seed_catalog(plan_repository, addon_repository)
    await plan_repository.set_price_override(
        SetPlanPriceOverrideDto(
            plan_id=plan.id,
            days=30,
            currency=Currency.RUB,
            price=Decimal("250"),
            anchor=Currency.USD,
        )
    )

    book = await AdjustBasePricesUseCase(
        plan_repository, addon_repository, pricing_repository, uow, event_publisher
    )(OWNER, AdjustBasePricesDto(scope=PriceAdjustScope.ALL_PLANS, factor=Decimal("1.1")))

    plan_row = next(row for row in book.plans if row.ref_id == plan.durations[0].id)
    assert plan_row.base_price == Decimal("2.20")  # 2.00 * 1.1
    addon_row = next(row for row in book.addons if row.ref_id == addon.id)
    assert addon_row.base_price == Decimal("1.00")  # untouched -- scope was ALL_PLANS

    # pinned override survives the base-price adjustment untouched
    rub_cell = next(c for c in plan_row.cells if c.currency is Currency.RUB)
    assert rub_cell.amount == Decimal("250")
    assert rub_cell.is_pinned is True


async def test_update_pricing_settings_persists(
    pricing_repository: PricingRepository, uow: UnitOfWork
) -> None:
    settings = await UpdatePricingSettingsUseCase(pricing_repository, uow)(
        OWNER, UpdatePricingSettingsDto(price_per_day=Decimal("0.50"), price_per_gb=Decimal("0.30"))
    )
    assert settings.price_per_day == Decimal("0.50")
    assert settings.price_per_gb == Decimal("0.30")
