from typing import List, Optional, Protocol, TypeVar, Union
from uuid import UUID

from packaging.version import Version
from remnapy.models import UserResponseDto
from remnapy.models.hwid import HwidDeviceDto

from src.application.dto import PlanSnapshotDto, RemnaSubscriptionDto, SubscriptionDto, UserDto

T = TypeVar("T", SubscriptionDto, RemnaSubscriptionDto)


class Remnawave(Protocol):
    async def try_connection(self) -> Version: ...

    async def create_user(
        self,
        user: UserDto,
        plan: Optional[PlanSnapshotDto] = None,
        subscription: Optional[SubscriptionDto] = None,
    ) -> UserResponseDto: ...

    async def update_user(
        self,
        user: UserDto,
        uuid: UUID,
        plan: Optional[PlanSnapshotDto] = None,
        subscription: Optional[SubscriptionDto] = None,
        reset_traffic: bool = False,
    ) -> UserResponseDto: ...

    async def delete_user(self, uuid: UUID) -> bool: ...

    async def get_user_by_uuid(self, uuid: UUID) -> Optional[UserResponseDto]: ...

    async def get_user_by_telegram_id(self, telegram_id: int) -> List[UserResponseDto]: ...

    async def get_all_users(self, limit: int, offset: int) -> List[UserResponseDto]: ...

    async def get_devices(self, uuid: UUID) -> List[HwidDeviceDto]: ...

    async def delete_device(self, user_uuid: UUID, hwid: str) -> Optional[int]: ...

    async def reset_traffic(self, uuid: UUID) -> Optional[UserResponseDto]: ...

    async def revoke_subscription(self, uuid: UUID) -> None: ...

    def apply_sync(
        self,
        target: T,
        source: Union[SubscriptionDto, RemnaSubscriptionDto],
    ) -> T: ...
