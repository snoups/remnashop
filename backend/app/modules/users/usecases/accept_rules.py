from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.users.dto import UserDto
from app.modules.users.events import UserRulesAcceptedEvent
from app.modules.users.repository import UserRepository


class AcceptRulesUseCase(UseCase[None, UserDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: None) -> UserDto:
        async with self._uow:
            user = await self._user_repository.set_rules_accepted_at(actor.id, datetime_now())
            await self._event_publisher.publish(UserRulesAcceptedEvent(user=user))
        logger.info(f"{actor.log} Accepted the rules")
        return user
