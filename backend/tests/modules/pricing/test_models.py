from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import CurrencyRate, PricingSettings
from app.core.enums import Currency, RoundingMode


async def test_currency_rate_roundtrip(session: AsyncSession) -> None:
    session.add(
        CurrencyRate(
            currency=Currency.RUB,
            rate=Decimal("95.0"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("10"),
        )
    )
    await session.flush()
    row = await session.scalar(select(CurrencyRate).where(CurrencyRate.currency == Currency.RUB))
    assert row is not None
    assert row.rate == Decimal("95.0")
    assert row.rounding_mode is RoundingMode.INTEGER


async def test_pricing_settings_singleton(session: AsyncSession) -> None:
    # a row committed by an earlier session would collide on id 1
    await session.execute(delete(PricingSettings))
    session.add(PricingSettings(id=1, anchor_currency=Currency.USD))
    await session.flush()
    row = await session.get(PricingSettings, 1)
    assert row is not None
    assert row.anchor_currency is Currency.USD
