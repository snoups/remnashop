from typing import Optional, Protocol, runtime_checkable

from src.application.dto import PaymentGatewayDto
from src.core.enums import PaymentGatewayType


@runtime_checkable
class PaymentGatewayDao(Protocol):
    async def create(self, gateway: PaymentGatewayDto) -> PaymentGatewayDto: ...

    async def get_by_id(self, gateway_id: int) -> Optional[PaymentGatewayDto]: ...

    async def get_by_type(
        self,
        gateway_type: PaymentGatewayType,
    ) -> Optional[PaymentGatewayDto]: ...

    async def get_active(self) -> list[PaymentGatewayDto]: ...

    async def get_all(
        self,
        only_active: bool = False,
        sorted: bool = True,
    ) -> list[PaymentGatewayDto]: ...

    async def update(self, gateway: PaymentGatewayDto) -> Optional[PaymentGatewayDto]: ...

    async def set_active_status(
        self,
        gateway_type: PaymentGatewayType,
        is_active: bool,
    ) -> None: ...

    async def count_active(self) -> int: ...
