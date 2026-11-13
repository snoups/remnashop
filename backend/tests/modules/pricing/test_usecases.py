import asyncio
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db.models.pricing_settings import PricingSettings
from app.core.db.models.transaction import Transaction
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    AddOnType,
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PinnedPriceAction,
    PlanType,
    PriceAdjustMode,
    PriceAdjustScope,
    PurchaseChannel,
    PurchaseType,
    Role,
    RoundingMode,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.outbox_event_publisher import OutboxEventPublisher
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.loyalty.dto import LoyaltyTierDto, UpdateLoyaltySettingsDto
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import (
    AddOnDto,
    AdjustBasePricesDto,
    CreateAddOnDto,
    CreatePlanDto,
    PlanDto,
    PriceBookDto,
    PricingChangePreviewDto,
    SetAddOnPriceOverrideDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    SetPlanPriceOverrideDto,
    SwitchAnchorCurrencyDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.plans.usecases import (
    AdjustBasePricesUseCase,
    GetPriceBookUseCase,
    PreviewPricingChangeUseCase,
    SwitchAnchorCurrencyUseCase,
)
from app.modules.pricing.dto import UpdateCurrencyRateDto
from app.modules.pricing.repository import PricingRepository
from app.modules.pricing.usecases import UpdateCurrencyRateUseCase
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.subscriptions.factories import make_plan_snapshot

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
        pricing_repository,
        plan_repository,
        addon_repository,
        TransactionRepository(plan_repository.session),
        LoyaltyRepository(plan_repository.session),
        uow,
        event_publisher,
    )(OWNER, SwitchAnchorCurrencyDto(new_anchor=Currency.RUB))
    after = await GetPriceBookUseCase(plan_repository, addon_repository, pricing_repository, uow)(
        OWNER
    )

    b = next(c for c in before.plans[0].cells if c.currency is Currency.RUB).amount
    a = next(row for row in after.plans if row.ref_id == duration_id)
    a_amount = next(c for c in a.cells if c.currency is Currency.RUB).amount
    assert abs(a_amount - b) <= Decimal("1")
    assert after.settings.anchor_currency is Currency.RUB


async def test_switch_anchor_turns_a_pin_in_the_new_anchor_into_the_base_price(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
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
    plan, addon = await _seed_catalog(plan_repository, addon_repository)
    duration_id = plan.durations[0].id
    for currency, price in ((Currency.RUB, Decimal("250")), (Currency.XTR, Decimal("150"))):
        await plan_repository.set_price_override(
            SetPlanPriceOverrideDto(plan_id=plan.id, days=30, currency=currency, price=price)
        )
    await addon_repository.set_price_override(
        SetAddOnPriceOverrideDto(addon_id=addon.id, currency=Currency.RUB, price=Decimal("120"))
    )
    transactions = TransactionRepository(session)
    loyalty = LoyaltyRepository(session)

    diff = await PreviewPricingChangeUseCase(
        plan_repository, addon_repository, pricing_repository, transactions, loyalty, uow
    )(OWNER, PricingChangePreviewDto(anchor=Currency.RUB))
    await SwitchAnchorCurrencyUseCase(
        pricing_repository,
        plan_repository,
        addon_repository,
        transactions,
        loyalty,
        uow,
        event_publisher,
    )(OWNER, SwitchAnchorCurrencyDto(new_anchor=Currency.RUB))
    book = await GetPriceBookUseCase(plan_repository, addon_repository, pricing_repository, uow)(
        OWNER
    )

    # the price buyers paid stays, now as the base the anchor column derives from
    assert not [row for row in diff.changes if row.currency is Currency.RUB]
    plan_row = next(row for row in book.plans if row.ref_id == duration_id)
    addon_row = next(row for row in book.addons if row.ref_id == addon.id)
    assert (plan_row.base_price, addon_row.base_price) == (Decimal("250"), Decimal("120"))
    cells = {c.currency: c for c in plan_row.cells}
    assert (cells[Currency.RUB].amount, cells[Currency.RUB].is_pinned) == (Decimal("250"), False)
    assert (cells[Currency.XTR].amount, cells[Currency.XTR].is_pinned) == (Decimal("150"), True)
    addon_rub = next(c for c in addon_row.cells if c.currency is Currency.RUB)
    assert addon_rub.is_pinned is False


async def test_switch_anchor_rescales_transaction_anchor_amounts(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    user_repository: UserRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    transaction_repository = TransactionRepository(session)
    await pricing_repository.get_rate_table()
    await pricing_repository.update_rate(
        UpdateCurrencyRateDto(
            currency=Currency.RUB,
            rate=Decimal("90"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("10"),
        )
    )
    buyer = await user_repository.create(CreateUserDto(name="buyer", telegram_id=950_001))
    async with uow:
        order = await transaction_repository.create(
            CreateTransactionDto(
                channel=PurchaseChannel.CABINET,
                user_id=buyer.id,
                plan_id=None,
                plan_snapshot=make_plan_snapshot(),
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                target_subscription_id=None,
                gateway_type=PaymentGatewayType.YOOKASSA,
                base_price=Decimal("900"),
                discount_percent=0,
                discount_source=DiscountSource.NONE,
                final_price=Decimal("900"),
                anchor_base_price=Decimal("10"),
                anchor_final_price=Decimal("10"),
                customer_email=None,
                idempotency_key=uuid4().hex,
                expires_at=datetime_now(),
            )
        )
    paid_at = datetime_now() - timedelta(days=40)
    await session.execute(
        update(Transaction).where(Transaction.id == order.id).values(updated_at=paid_at)
    )

    await SwitchAnchorCurrencyUseCase(
        pricing_repository,
        plan_repository,
        addon_repository,
        transaction_repository,
        LoyaltyRepository(session),
        uow,
        event_publisher,
    )(OWNER, SwitchAnchorCurrencyDto(new_anchor=Currency.RUB))

    session.expire_all()
    after = await transaction_repository.get_by_id(order.id)
    assert after.anchor_base_price == Decimal("900")
    assert after.anchor_final_price == Decimal("900")
    assert (after.final_price, after.currency) == (Decimal("900"), Currency.RUB)
    assert after.updated_at == paid_at


async def test_switch_anchor_rescales_loyalty_thresholds(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await pricing_repository.get_rate_table()
    await pricing_repository.update_rate(
        UpdateCurrencyRateDto(
            currency=Currency.RUB,
            rate=Decimal("90"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("10"),
        )
    )
    loyalty = LoyaltyRepository(session)
    await loyalty.save_settings(
        UpdateLoyaltySettingsDto(
            enabled=True,
            window_months=None,
            tiers=[LoyaltyTierDto(threshold=Decimal("10"), percent=3)],
        )
    )

    await SwitchAnchorCurrencyUseCase(
        pricing_repository,
        plan_repository,
        addon_repository,
        TransactionRepository(session),
        loyalty,
        uow,
        event_publisher,
    )(OWNER, SwitchAnchorCurrencyDto(new_anchor=Currency.RUB))

    assert (await loyalty.get_settings()).tiers == [
        LoyaltyTierDto(threshold=Decimal("900"), percent=3)
    ]


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
        plan_repository,
        addon_repository,
        pricing_repository,
        TransactionRepository(plan_repository.session),
        LoyaltyRepository(plan_repository.session),
        uow,
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
    # plain names plus days: the client builds "30 дн." / "30d" in its own language
    plan_rows = [row for row in diff.changes if row.days is not None]
    addon_rows = [row for row in diff.changes if row.days is None]
    assert {row.name for row in plan_rows} == {plan.name}
    assert {row.days for row in plan_rows} == {d.days for d in plan.durations}
    assert {row.name for row in addon_rows} == {addon.name}

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
        plan_repository,
        addon_repository,
        pricing_repository,
        TransactionRepository(plan_repository.session),
        LoyaltyRepository(plan_repository.session),
        uow,
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
        )
    )

    book = await AdjustBasePricesUseCase(
        plan_repository, addon_repository, pricing_repository, uow, event_publisher
    )(OWNER, AdjustBasePricesDto(scope=PriceAdjustScope.ALL_PLANS, factor=Decimal("1.1")))

    plan_row = next(row for row in book.plans if row.ref_id == plan.durations[0].id)
    assert plan_row.base_price == Decimal("2.20")  # 2.00 * 1.1
    addon_row = next(row for row in book.addons if row.ref_id == addon.id)
    assert addon_row.base_price == Decimal("1.00")  # scope was ALL_PLANS

    # pinned override survives the base-price adjustment untouched
    rub_cell = next(c for c in plan_row.cells if c.currency is Currency.RUB)
    assert rub_cell.amount == Decimal("250")
    assert rub_cell.is_pinned is True


async def test_adjust_base_prices_selected_touches_only_the_listed_durations(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await pricing_repository.get_rate_table()
    plan, addon = await _seed_catalog(plan_repository, addon_repository)
    other = await plan_repository.create(
        CreatePlanDto(
            public_code="other",
            name="Other",
            type=PlanType.UNLIMITED,
            traffic_limit=0,
            device_limit=0,
        )
    )
    other = await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=other.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("5.00"))],
        )
    )

    book = await AdjustBasePricesUseCase(
        plan_repository, addon_repository, pricing_repository, uow, event_publisher
    )(
        OWNER,
        AdjustBasePricesDto(
            scope=PriceAdjustScope.SELECTED,
            factor=Decimal("2"),
            plan_duration_ids=[duration.id for duration in plan.durations],
        ),
    )

    prices = {row.ref_id: row.base_price for row in book.plans}
    assert prices[plan.durations[0].id] == Decimal("4.00")
    assert prices[other.durations[0].id] == Decimal("5.00")
    assert next(row for row in book.addons if row.ref_id == addon.id).base_price == Decimal("1.00")


async def _seed_ladder_plan(plan_repository: PlanRepository) -> PlanDto:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="ladder",
            name="Ladder",
            type=PlanType.UNLIMITED,
            traffic_limit=0,
            device_limit=0,
        )
    )
    return await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[
                SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("1.00")),
                SetPlanDurationDto(days=90, order_index=1, base_price=Decimal("1.00")),
            ],
        )
    )


async def test_adjust_ladder_prices_durations_from_the_30_day_price(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await pricing_repository.get_rate_table()
    plan = await _seed_ladder_plan(plan_repository)

    book = await AdjustBasePricesUseCase(
        plan_repository, addon_repository, pricing_repository, uow, event_publisher
    )(
        OWNER,
        AdjustBasePricesDto(
            scope=PriceAdjustScope.SELECTED,
            mode=PriceAdjustMode.LADDER,
            price=Decimal("3.00"),
            ladder_discounts={90: Decimal("10")},
            plan_duration_ids=[duration.id for duration in plan.durations],
        ),
    )

    prices = {row.days: row.base_price for row in book.plans if row.plan_id == plan.id}
    assert prices == {30: Decimal("3.00"), 90: Decimal("8.10")}  # 3 * 3 months - 10%


async def test_adjust_set_price_scales_or_resets_pins(
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
            plan_id=plan.id, days=30, currency=Currency.RUB, price=Decimal("250")
        )
    )
    use_case = AdjustBasePricesUseCase(
        plan_repository, addon_repository, pricing_repository, uow, event_publisher
    )

    def _rub(book: PriceBookDto) -> Decimal:
        row = next(row for row in book.plans if row.ref_id == plan.durations[0].id)
        assert row.base_price == Decimal("4.00")
        return next(cell for cell in row.cells if cell.currency is Currency.RUB).amount

    scaled = await use_case(
        OWNER,
        AdjustBasePricesDto(
            scope=PriceAdjustScope.ALL_PLANS,
            mode=PriceAdjustMode.SET,
            price=Decimal("4.00"),
            pinned=PinnedPriceAction.SCALE,
        ),
    )
    assert _rub(scaled) == Decimal("500")  # base 2.00 -> 4.00 doubles the pin

    reset = await use_case(
        OWNER,
        AdjustBasePricesDto(
            scope=PriceAdjustScope.ALL_PLANS,
            mode=PriceAdjustMode.SET,
            price=Decimal("4.00"),
            pinned=PinnedPriceAction.RESET,
        ),
    )
    row = next(row for row in reset.plans if row.ref_id == plan.durations[0].id)
    assert not any(cell.is_pinned for cell in row.cells)


async def test_adjust_ladder_from_a_long_base_marks_up_a_shorter_duration(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await pricing_repository.get_rate_table()
    plan = await _seed_ladder_plan(plan_repository)

    book = await AdjustBasePricesUseCase(
        plan_repository, addon_repository, pricing_repository, uow, event_publisher
    )(
        OWNER,
        AdjustBasePricesDto(
            scope=PriceAdjustScope.SELECTED,
            mode=PriceAdjustMode.LADDER,
            price=Decimal("9.00"),
            ladder_base_days=90,
            ladder_discounts={30: Decimal("-50")},
            plan_duration_ids=[duration.id for duration in plan.durations],
        ),
    )

    prices = {row.days: row.base_price for row in book.plans if row.plan_id == plan.id}
    assert prices == {30: Decimal("4.50"), 90: Decimal("9.00")}  # a third of 9.00, +50%


async def test_anchor_switch_rechecks_the_anchor_under_the_row_lock(engine: AsyncEngine) -> None:
    # A concurrent switch commits while this one runs. Only the committed
    # settings column is touched (and restored); the switcher's own writes stay
    # in a rolled-back transaction.
    async with AsyncSession(engine) as setup:
        existed = await setup.get(PricingSettings, 1) is not None
        settings = await PricingRepository(setup).get_settings()
        await setup.commit()
    original = settings.anchor_currency
    target = Currency.RUB if original is not Currency.RUB else Currency.USD

    async with engine.connect() as holder_conn, engine.connect() as switch_conn:
        holder = AsyncSession(bind=holder_conn)
        await holder.execute(
            update(PricingSettings)
            .where(PricingSettings.id == settings.id)
            .values(anchor_currency=target)
        )

        await switch_conn.begin()
        switcher = AsyncSession(
            bind=switch_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        uow = UnitOfWork(switcher)
        use_case = SwitchAnchorCurrencyUseCase(
            PricingRepository(switcher),
            PlanRepository(switcher),
            AddOnRepository(switcher),
            TransactionRepository(switcher),
            LoyaltyRepository(switcher),
            uow,
            OutboxEventPublisher(uow, RecordingDispatch()),
        )
        switch = asyncio.create_task(use_case(OWNER, SwitchAnchorCurrencyDto(new_anchor=target)))
        try:
            await asyncio.sleep(0.3)
            await holder.commit()

            with pytest.raises(ValidationError) as error:
                await switch
            assert error.value.code is ErrorCode.ANCHOR_CURRENCY_UNCHANGED
        finally:
            if not switch.done():
                switch.cancel()
            await switch_conn.rollback()
            restore = (
                update(PricingSettings).values(anchor_currency=original)
                if existed
                else delete(PricingSettings)
            )
            await holder.execute(restore.where(PricingSettings.id == settings.id))
            await holder.commit()


def _book_amounts(book) -> dict[tuple[str, object, Currency], Decimal]:  # type: ignore[no-untyped-def]
    return {
        (row.name, row.days, cell.currency): cell.amount
        for row in [*book.plans, *book.addons]
        for cell in row.cells
    }


@pytest.mark.parametrize("change", ["adjust", "anchor"])
async def test_preview_shows_what_applying_the_change_does(
    change: str,
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
    plan, addon = await _seed_catalog(plan_repository, addon_repository)
    adjust = AdjustBasePricesDto(
        scope=PriceAdjustScope.SELECTED,
        factor=Decimal("1.37"),
        plan_duration_ids=[plan.durations[0].id],
        addon_ids=[addon.id],
    )
    preview = (
        PricingChangePreviewDto(adjust=adjust)
        if change == "adjust"
        else (PricingChangePreviewDto(anchor=Currency.RUB))
    )
    before = _book_amounts(
        await GetPriceBookUseCase(plan_repository, addon_repository, pricing_repository, uow)(OWNER)
    )

    diff = await PreviewPricingChangeUseCase(
        plan_repository,
        addon_repository,
        pricing_repository,
        TransactionRepository(plan_repository.session),
        LoyaltyRepository(plan_repository.session),
        uow,
    )(OWNER, preview)
    if change == "adjust":
        book = await AdjustBasePricesUseCase(
            plan_repository, addon_repository, pricing_repository, uow, event_publisher
        )(OWNER, adjust)
    else:
        book = await SwitchAnchorCurrencyUseCase(
            pricing_repository,
            plan_repository,
            addon_repository,
            TransactionRepository(plan_repository.session),
            LoyaltyRepository(plan_repository.session),
            uow,
            event_publisher,
        )(OWNER, SwitchAnchorCurrencyDto(new_anchor=Currency.RUB))
    after = _book_amounts(book)

    changed = {key: amount for key, amount in after.items() if before.get(key) != amount}
    # an anchor switch keeps every derived amount; an adjustment must move some
    assert bool(changed) is (change == "adjust")
    assert {(row.name, row.days, row.currency): row.new for row in diff.changes} == changed


async def test_anchor_preview_shows_the_values_the_switch_rescales(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await pricing_repository.get_rate_table()
    await pricing_repository.update_rate(
        UpdateCurrencyRateDto(
            currency=Currency.RUB,
            rate=Decimal("90"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("10"),
        )
    )
    loyalty = LoyaltyRepository(session)
    await loyalty.save_settings(
        UpdateLoyaltySettingsDto(
            enabled=True,
            window_months=None,
            tiers=[LoyaltyTierDto(threshold=Decimal("10.05"), percent=3)],
        )
    )
    transactions = TransactionRepository(session)

    diff = await PreviewPricingChangeUseCase(
        plan_repository, addon_repository, pricing_repository, transactions, loyalty, uow
    )(OWNER, PricingChangePreviewDto(anchor=Currency.RUB))
    await SwitchAnchorCurrencyUseCase(
        pricing_repository,
        plan_repository,
        addon_repository,
        transactions,
        loyalty,
        uow,
        event_publisher,
    )(OWNER, SwitchAnchorCurrencyDto(new_anchor=Currency.RUB))

    assert [(t.old, t.new) for t in diff.loyalty_thresholds] == [
        (Decimal("10.05"), tier.threshold) for tier in (await loyalty.get_settings()).tiers
    ]
    assert diff.rescaled_transactions == await transactions.count_anchor_amounts()


async def test_non_anchor_preview_leaves_the_anchor_fields_empty(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    await pricing_repository.get_rate_table()
    await _seed_catalog(plan_repository, addon_repository)

    diff = await PreviewPricingChangeUseCase(
        plan_repository,
        addon_repository,
        pricing_repository,
        TransactionRepository(session),
        LoyaltyRepository(session),
        uow,
    )(
        OWNER,
        PricingChangePreviewDto(
            adjust=AdjustBasePricesDto(scope=PriceAdjustScope.ALL_PLANS, factor=Decimal("2"))
        ),
    )

    assert diff.changes
    assert diff.loyalty_thresholds == []
    assert diff.rescaled_transactions == 0


async def test_price_book_marks_a_free_trial_and_prices_it_at_zero(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="try",
            name="Trial",
            type=PlanType.BOTH,
            traffic_limit=10,
            device_limit=1,
            is_trial=True,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[SetPlanDurationDto(days=3, order_index=0, base_price=Decimal("0"))],
        )
    )
    paid, _ = await _seed_catalog(plan_repository, addon_repository)

    book = await GetPriceBookUseCase(plan_repository, addon_repository, pricing_repository, uow)(
        OWNER
    )

    trial_row = next(row for row in book.plans if row.plan_id == created.id)
    assert trial_row.is_free_trial is True
    assert all(cell.amount == 0 for cell in trial_row.cells)
    assert next(row for row in book.plans if row.plan_id == paid.id).is_free_trial is False


async def test_adjust_base_prices_leaves_a_free_trial_free(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    trial = await plan_repository.create(
        CreatePlanDto(
            public_code="try",
            name="Trial",
            type=PlanType.BOTH,
            traffic_limit=10,
            device_limit=1,
            is_trial=True,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=trial.id,
            durations=[SetPlanDurationDto(days=3, order_index=0, base_price=Decimal("0"))],
        )
    )
    paid, _ = await _seed_catalog(plan_repository, addon_repository)

    book = await AdjustBasePricesUseCase(
        plan_repository, addon_repository, pricing_repository, uow, event_publisher
    )(
        OWNER,
        AdjustBasePricesDto(
            scope=PriceAdjustScope.ALL_PLANS, mode=PriceAdjustMode.SET, price=Decimal("300")
        ),
    )

    prices = {row.plan_id: row.base_price for row in book.plans}
    assert prices[trial.id] == Decimal("0")
    assert prices[paid.id] == Decimal("300")
