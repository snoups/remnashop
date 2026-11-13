from decimal import Decimal
from typing import Final

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.currency_rate import CurrencyRate
from app.core.db.models.pricing_settings import PricingSettings
from app.core.db.singleton import SINGLETON_ID, get_or_create_singleton
from app.core.enums import Currency, RoundingMode
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.pricing.dto import (
    RATE_PRECISION,
    CurrencyRateDto,
    CurrencyRateTable,
    PricingSettingsDto,
    UpdateCurrencyRateDto,
)

# rate is per 1 USD (the default anchor): RUB at Steam's in-game rate, XTR at
# Telegram's ~$0.013 payout per star
_SEED_RATES: Final[dict[Currency, tuple[Decimal, RoundingMode, None, Decimal]]] = {
    Currency.USD: (Decimal("1"), RoundingMode.DECIMAL_2, None, Decimal("0.01")),
    Currency.RUB: (Decimal("85"), RoundingMode.INTEGER, None, Decimal("10")),
    Currency.XTR: (Decimal("77"), RoundingMode.INTEGER, None, Decimal("1")),
}


class PricingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_rate_dto(self, row: CurrencyRate) -> CurrencyRateDto:
        return CurrencyRateDto.model_validate(row, from_attributes=True)

    def _to_settings_dto(self, row: PricingSettings) -> PricingSettingsDto:
        return PricingSettingsDto.model_validate(row, from_attributes=True)

    async def _get_or_create_settings(self) -> PricingSettings:
        return await get_or_create_singleton(self.session, PricingSettings, SINGLETON_ID)

    async def _seed_missing_rates(self, missing: list[Currency], anchor: Currency) -> None:
        # the seed is per 1 USD: rebased so the anchor is 1, as switching the anchor
        # leaves it (a migrated shop starts on its own anchor, RUB say)
        per_anchor = _SEED_RATES[anchor][0]
        # ON CONFLICT DO NOTHING, not session.add: the same fresh-database race
        # get_or_create_singleton guards against
        await self.session.execute(
            pg_insert(CurrencyRate)
            .values(
                [
                    {
                        "currency": currency,
                        "rate": (_SEED_RATES[currency][0] / per_anchor).quantize(RATE_PRECISION),
                        "rounding_mode": _SEED_RATES[currency][1],
                        "charm_ending": _SEED_RATES[currency][2],
                        "min_amount": _SEED_RATES[currency][3],
                    }
                    for currency in missing
                ]
            )
            .on_conflict_do_nothing()
        )

    async def get_rate_table(self) -> CurrencyRateTable:
        result = await self.session.execute(select(CurrencyRate))
        rows = {row.currency: row for row in result.scalars()}

        settings = await self._get_or_create_settings()
        missing = [currency for currency in _SEED_RATES if currency not in rows]
        if missing:
            await self._seed_missing_rates(missing, settings.anchor_currency)
            result = await self.session.execute(select(CurrencyRate))
            rows = {row.currency: row for row in result.scalars()}

        return CurrencyRateTable(
            anchor=settings.anchor_currency,
            rows={currency: self._to_rate_dto(row) for currency, row in rows.items()},
        )

    async def lock_settings(self) -> None:
        # serializes anchor switches: the anchor is re-read after this returns
        settings = await self._get_or_create_settings()
        await self.session.execute(
            select(PricingSettings)
            .where(PricingSettings.id == settings.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def get_settings(self) -> PricingSettingsDto:
        settings = await self._get_or_create_settings()
        await self.session.flush()
        return self._to_settings_dto(settings)

    async def update_rate(self, data: UpdateCurrencyRateDto) -> CurrencyRateDto:
        # an anchor switch rescales every rate under this lock; a concurrent edit must wait for it
        await self.lock_settings()
        settings = await self._get_or_create_settings()
        if data.currency == settings.anchor_currency and data.rate != 1:
            raise ValidationError(
                "The anchor currency's rate is fixed at 1.0", code=ErrorCode.ANCHOR_RATE_FIXED
            )

        row = await self.session.get(CurrencyRate, data.currency)
        if row is None:
            raise ValidationError(
                f"No currency rate row for {data.currency}", code=ErrorCode.CURRENCY_RATE_MISSING
            )

        row.rate = data.rate.quantize(RATE_PRECISION)
        row.rounding_mode = data.rounding_mode
        row.charm_ending = data.charm_ending
        row.min_amount = data.min_amount

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_rate_dto(row)

    async def set_anchor(self, new_anchor: Currency, new_rates: dict[Currency, Decimal]) -> None:
        settings = await self._get_or_create_settings()
        settings.anchor_currency = new_anchor

        for currency, rate in new_rates.items():
            row = await self.session.get(CurrencyRate, currency)
            if row is None:
                raise ValidationError(
                    f"No currency rate row for {currency}", code=ErrorCode.CURRENCY_RATE_MISSING
                )
            row.rate = rate

        await self.session.flush()
