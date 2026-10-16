from typing import Optional

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.modules.users.dto import UserDto
from app.modules.users.repository import UserRepository


class FindTelegramUserUseCase(UseCase[int, Optional[UserDto]]):
    # the bot looking up who wrote to it; callable only via `.system`
    required_permission = None

    def __init__(self, user_repository: UserRepository, uow: UnitOfWork) -> None:
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> Optional[UserDto]:
        async with self._uow:
            return await self._user_repository.get_by_telegram_id(data)
