from decimal import Decimal
from typing import Protocol


class PlanReferenceCleaner(Protocol):
    async def forget_plan(self, plan_id: int) -> None: ...


class AnchorAmountRescaler(Protocol):
    async def rescale_anchor_amounts(self, factor: Decimal) -> None: ...


class LoyaltyThresholdRescaler(Protocol):
    async def rescale_thresholds(self, factor: Decimal) -> None: ...
