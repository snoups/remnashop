from typing import Optional, Protocol, runtime_checkable

from src.application.dto import PromocodeActivationDto, PromocodeDto


@runtime_checkable
class PromocodeDao(Protocol):
    async def create(self, promocode: PromocodeDto) -> PromocodeDto: ...

    async def get_by_id(self, promocode_id: int) -> Optional[PromocodeDto]: ...

    async def get_by_code(self, code: str) -> Optional[PromocodeDto]: ...

    async def deactivate(self, promocode_id: int) -> None: ...

    async def count_activations(self, promocode_id: int) -> int: ...

    async def has_user_activated(self, promocode_id: int, user_telegram_id: int) -> bool: ...

    async def record_activation(
        self,
        activation: PromocodeActivationDto,
    ) -> PromocodeActivationDto: ...

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PromocodeDto]: ...
