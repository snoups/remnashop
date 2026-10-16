from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import ClearEmailUndeliverableDto, UserDto
from app.modules.users.events import UserEmailUndeliverableClearedEvent
from app.modules.users.repository import UserRepository
from app.modules.users.visibility import assert_manageable, get_visible_target


class ClearEmailUndeliverableUseCase(UseCase[ClearEmailUndeliverableDto, UserDto]):
    required_permission = Permission.USERS_EMAIL_UNDELIVERABLE_CLEAR

    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: ClearEmailUndeliverableDto) -> UserDto:
        async with self._uow:
            target = await get_visible_target(
                self._user_repository, actor, data.user_id, for_update=True
            )
            assert_manageable(actor, target)

            await self._user_repository.set_email_undeliverable(data.user_id, None)
            updated = await self._user_repository.find_by_id(data.user_id)
            if updated is None:
                raise NotFoundError(f"User {data.user_id} not found", code=ErrorCode.USER_NOT_FOUND)
            await self._event_publisher.publish(
                UserEmailUndeliverableClearedEvent(
                    actor=actor, target=updated, ip_address=data.client_ip
                )
            )
        logger.info(f"{actor.log} Cleared undeliverable email of user '{data.user_id}'")
        return updated
