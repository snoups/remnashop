from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.users.bot_blocked import mark_bot_blocked
from app.modules.users.dto import SetBotBlockedDto
from app.modules.users.repository import UserRepository


class SetBotBlockedUseCase(UseCase[SetBotBlockedDto, None]):
    required_permission = None

    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: SetBotBlockedDto) -> None:
        async with self._uow:
            user = await self._user_repository.get_by_telegram_id(data.telegram_id)
            if user is None:
                return
            if data.blocked:
                await mark_bot_blocked(self._user_repository, self._event_publisher, user.id)
            else:
                await self._user_repository.set_bot_blocked(user.id, False)
        logger.info(f"User '{user.id}' bot blocked status set to {data.blocked}")
