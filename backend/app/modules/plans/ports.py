from decimal import Decimal
from typing import Protocol

from app.modules.plans.dto import ScaledAmountDto


class PlanReferenceCleaner(Protocol):
    async def forget_plan(self, plan_id: int) -> list[int]: ...


class AnchorAmountRescaler(Protocol):
    async def rescale_anchor_amounts(self, factor: Decimal) -> None: ...

    async def count_anchor_amounts(self) -> int: ...


class LoyaltyThresholdRescaler(Protocol):
    async def rescale_thresholds(self, factor: Decimal) -> None: ...

    async def preview_rescaled_thresholds(self, factor: Decimal) -> list[ScaledAmountDto]: ...
