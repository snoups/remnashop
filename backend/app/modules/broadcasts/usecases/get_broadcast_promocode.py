from typing import Optional

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.validation import promocode_is_usable
from app.modules.promocodes import PromocodeRepository
from app.modules.users import UserDto


class GetBroadcastPromocodeUseCase(UseCase[int, Optional[str], UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        promocode_repository: PromocodeRepository,
        uow: UnitOfWork,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._promocode_repository = promocode_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> Optional[str]:
        async with self._uow:
            broadcast = await self._broadcast_repository.find_by_id(data)
            if broadcast is None or broadcast.started_at is None or broadcast.promocode_id is None:
                return None
            if (
                broadcast.channel_message_id is None
                and not await self._broadcast_repository.is_recipient(data, actor.id)
            ):
                return None
            return await promocode_is_usable(self._promocode_repository, broadcast.promocode_id)
