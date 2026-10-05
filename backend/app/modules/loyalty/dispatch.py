from typing import Optional, Protocol


class LoyaltyRecalcDispatch(Protocol):
    async def kiq(self, *, user_ids: Optional[list[int]] = None) -> object: ...
