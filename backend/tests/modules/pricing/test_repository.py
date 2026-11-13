import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db.models.currency_rate import CurrencyRate
from app.core.db.models.pricing_settings import PricingSettings
from app.core.db.singleton import SINGLETON_ID
from app.core.enums import Currency, RoundingMode
from app.core.exceptions import ValidationError
from app.modules.pricing import repository as repository_module
from app.modules.pricing.dto import UpdateCurrencyRateDto, UpdatePricingSettingsDto
from app.modules.pricing.repository import PricingRepository
from app.modules.pricing.resolver import resolve_price


async def test_get_rate_table_seeds_three_rows(session: AsyncSession) -> None:
    repo = PricingRepository(session)
    table = await repo.get_rate_table()
    assert table.anchor is Currency.USD
    assert set(table.rows) == {Currency.USD, Currency.XTR, Currency.RUB}
    assert table.rows[Currency.USD].rate == Decimal("1.000000")
    assert table.rows[Currency.XTR].min_amount == Decimal("1.00")


async def test_get_rate_table_is_idempotent(session: AsyncSession) -> None:
    repo = PricingRepository(session)
    await repo.get_rate_table()
    await repo.get_rate_table()
    table = await repo.get_rate_table()
    assert len(table.rows) == 3


async def test_update_rate_changes_a_row(session: AsyncSession) -> None:
    repo = PricingRepository(session)
    await repo.get_rate_table()
    await repo.update_rate(
        UpdateCurrencyRateDto(
            currency=Currency.RUB,
            rate=Decimal("95"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=99,
            min_amount=Decimal("10"),
        )
    )
    table = await repo.get_rate_table()
    assert table.rows[Currency.RUB].rate == Decimal("95.000000")
    assert table.rows[Currency.RUB].charm_ending == 99


async def test_update_rate_rejects_nonunit_anchor_rate(session: AsyncSession) -> None:
    repo = PricingRepository(session)
    await repo.get_rate_table()
    with pytest.raises(ValidationError):
        await repo.update_rate(
            UpdateCurrencyRateDto(
                currency=Currency.USD,
                rate=Decimal("2"),
                rounding_mode=RoundingMode.DECIMAL_2,
                charm_ending=None,
                min_amount=Decimal("0.01"),
            )
        )


async def test_update_settings_sets_dynamic_rates(session: AsyncSession) -> None:
    repo = PricingRepository(session)
    await repo.get_rate_table()
    result = await repo.update_settings(
        UpdatePricingSettingsDto(price_per_day=Decimal("0.30"), price_per_gb=Decimal("0.10"))
    )
    assert result.price_per_day == Decimal("0.30")


async def test_update_settings_clears_a_field_to_null(session: AsyncSession) -> None:
    repo = PricingRepository(session)
    await repo.get_rate_table()
    await repo.update_settings(
        UpdatePricingSettingsDto(price_per_day=Decimal("0.30"), price_per_gb=Decimal("0.10"))
    )
    result = await repo.update_settings(
        UpdatePricingSettingsDto(price_per_day=None, price_per_gb=Decimal("0.10"))
    )
    assert result.price_per_day is None
    assert result.price_per_gb == Decimal("0.10")


async def test_get_rate_table_survives_concurrent_seeding(engine: AsyncEngine) -> None:
    # real connections, not the rolled-back `session`: the race needs two
    # transactions inserting the same seed rows
    async def seed() -> None:
        async with AsyncSession(engine) as concurrent:
            await PricingRepository(concurrent).get_rate_table()
            await concurrent.commit()

    try:
        await asyncio.gather(seed(), seed(), seed())
    finally:
        async with AsyncSession(engine) as cleanup:
            await cleanup.execute(delete(CurrencyRate))
            await cleanup.execute(delete(PricingSettings))
            await cleanup.commit()


async def test_update_rate_takes_the_settings_lock_first(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = PricingRepository(session)
    await repo.get_rate_table()
    calls: list[str] = []
    real_lock = repo.lock_settings

    async def _recording_lock() -> None:
        calls.append("lock")
        await real_lock()

    monkeypatch.setattr(repo, "lock_settings", _recording_lock)
    table = await repo.get_rate_table()
    other = next(c for c in table.rows if c is not table.anchor)

    await repo.update_rate(
        UpdateCurrencyRateDto(
            currency=other,
            rate=Decimal("2"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("1"),
        )
    )

    assert calls == ["lock"]


async def test_rates_seeded_after_a_migration_are_per_its_anchor(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the production seed is per 1 USD; a migrated shop's anchor is already RUB
    monkeypatch.setattr(
        repository_module,
        "_SEED_RATES",
        {
            Currency.USD: (Decimal("1"), RoundingMode.DECIMAL_2, None, Decimal("0.01")),
            Currency.RUB: (Decimal("85"), RoundingMode.INTEGER, None, Decimal("10")),
            Currency.XTR: (Decimal("77"), RoundingMode.INTEGER, None, Decimal("1")),
        },
    )
    session.add(PricingSettings(id=SINGLETON_ID, anchor_currency=Currency.RUB))
    await session.flush()

    table = await PricingRepository(session).get_rate_table()

    assert table.rows[Currency.RUB].rate == Decimal("1.000000")
    assert table.rows[Currency.USD].rate == Decimal("0.011765")
    assert table.rows[Currency.XTR].rate == Decimal("0.905882")
    assert resolve_price(Decimal("500"), Currency.RUB, None, table) == Decimal("500")
