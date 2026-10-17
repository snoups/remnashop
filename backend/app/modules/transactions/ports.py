from typing import Protocol


class PromocodeLiveness(Protocol):
    async def is_live(self, promocode_id: int) -> bool: ...
