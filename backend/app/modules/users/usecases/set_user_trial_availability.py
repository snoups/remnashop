from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import SetUserTrialAvailabilityDto, UpdateUserDto, UserListItemDto
from app.modules.users.events import UserTrialAvailabilityChangedEvent
from app.modules.users.listing import detail_roles
from app.modules.users.repository import UserRepository
from app.modules.users.visibility import assert_manageable, get_visible_target


class SetUserTrialAvailabilityUseCase(UseCase[SetUserTrialAvailabilityDto, UserListItemDto]):
    required_permission = Permission.USERS_TRIAL_MANAGE

    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: SetUserTrialAvailabilityDto) -> UserListItemDto:
        async with self._uow:
            target = await get_visible_target(
                self._user_repository, actor, data.user_id, for_update=True
            )
            assert_manageable(actor, target)

            if target.is_trial_available != data.is_trial_available:
                updated = await self._user_repository.update_fields(
                    target.id, UpdateUserDto(is_trial_available=data.is_trial_available)
                )
                if updated is None:
                    raise NotFoundError(
                        f"User '{data.user_id}' not found", code=ErrorCode.USER_NOT_FOUND
                    )
                await self._event_publisher.publish(
                    UserTrialAvailabilityChangedEvent(
                        actor=actor,
                        target=updated,
                        is_trial_available=updated.is_trial_available,
                        ip_address=data.client_ip,
                    )
                )
                logger.info(
                    f"{actor.log} Set trial availability of user '{data.user_id}' "
                    f"to {data.is_trial_available}"
                )
            return await self._user_repository.get_list_item(
                target.id, detail_roles(actor, target.id)
            )
