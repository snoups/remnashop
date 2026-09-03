from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Currency, RoundingMode
from app.core.exceptions import ValidationError
from app.modules.pricing.dto import UpdateCurrencyRateDto, UpdatePricingSettingsDto
from app.modules.pricing.repository import PricingRepository


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
