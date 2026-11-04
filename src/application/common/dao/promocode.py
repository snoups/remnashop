from typing import Optional, Protocol, runtime_checkable

from src.application.dto import (
    PromocodeActivationDto,
    PromocodeDetailStatisticsDto,
    PromocodeDto,
    PromocodeStatisticsDto,
)


@runtime_checkable
class PromocodeDao(Protocol):
    async def create(self, promocode: PromocodeDto) -> PromocodeDto: ...

    async def update(self, promocode: PromocodeDto) -> Optional[PromocodeDto]: ...

    async def delete(self, promocode_id: int) -> bool: ...

    async def get_by_id(self, promocode_id: int) -> Optional[PromocodeDto]: ...

    async def get_by_code(self, code: str) -> Optional[PromocodeDto]: ...

    async def get_list(self, limit: int = 100, offset: int = 0) -> list[PromocodeDto]: ...

    async def get_activations_count(self, promocode_id: int) -> int: ...

    async def get_statistics(self) -> PromocodeStatisticsDto: ...

    async def get_detail_statistics(
        self, promocode_id: int
    ) -> Optional[PromocodeDetailStatisticsDto]: ...

    async def get_activation_by_user(
        self, promocode_id: int, user_id: int
    ) -> Optional[PromocodeActivationDto]: ...

    async def create_activation(
        self,
        activation: PromocodeActivationDto,
        max_activations: Optional[int] = None,
        is_reusable: bool = False,
    ) -> PromocodeActivationDto: ...
