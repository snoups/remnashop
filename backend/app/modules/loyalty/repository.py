from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ONE_CENT
from app.core.db.models.loyalty_settings import LoyaltySettings
from app.core.db.singleton import SINGLETON_ID, get_or_create_singleton
from app.modules.loyalty.dto import LoyaltySettingsDto, LoyaltyTierDto, UpdateLoyaltySettingsDto


class LoyaltyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: Optional[LoyaltySettings]) -> LoyaltySettingsDto:
        if row is None:
            return LoyaltySettingsDto()
        return LoyaltySettingsDto(
            enabled=row.enabled,
            window_months=row.window_months,
            tiers=[
                LoyaltyTierDto(threshold=Decimal(tier["threshold"]), percent=int(tier["percent"]))
                for tier in row.tiers
            ],
        )

    async def get_settings(self) -> LoyaltySettingsDto:
        return self._to_dto(await self.session.get(LoyaltySettings, SINGLETON_ID))

    async def save_settings(self, data: UpdateLoyaltySettingsDto) -> LoyaltySettingsDto:
        row = await get_or_create_singleton(self.session, LoyaltySettings, SINGLETON_ID, tiers=[])
        row.enabled = data.enabled
        row.window_months = data.window_months
        row.tiers = [
            {"threshold": str(tier.threshold.quantize(ONE_CENT)), "percent": tier.percent}
            for tier in data.tiers
        ]
        await self.session.flush()
        return self._to_dto(row)

    async def rescale_thresholds(self, factor: Decimal) -> None:
        row = await self.session.get(LoyaltySettings, SINGLETON_ID)
        if row is None or not row.tiers:
            return
        row.tiers = [
            {**tier, "threshold": str((Decimal(tier["threshold"]) * factor).quantize(ONE_CENT))}
            for tier in row.tiers
        ]
        await self.session.flush()
