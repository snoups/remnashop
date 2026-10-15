from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.http import is_ip_allowed
from app.modules.users.dto import UpdateSecuritySettingsDto, UpdateUserDto, UserDto
from app.modules.users.events import SecuritySettingsChangedEvent
from app.modules.users.repository import UserRepository


class UpdateOwnSecuritySettingsUseCase(UseCase[UpdateSecuritySettingsDto, UserDto, UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: UpdateSecuritySettingsDto) -> UserDto:
        if data.ip_allowlist and not is_ip_allowed(data.client_ip, data.ip_allowlist):
            raise ValidationError(
                "Your current IP is not in the submitted allowlist -- this would lock you out",
                code=ErrorCode.IP_ALLOWLIST_LOCKOUT,
            )

        async with self._uow:
            updated = await self._user_repository.update_fields(
                actor.id, UpdateUserDto(ip_allowlist=list(data.ip_allowlist))
            )
            await self._event_publisher.publish(
                SecuritySettingsChangedEvent(
                    user=actor, changed_fields=["ip_allowlist"], ip_address=data.client_ip
                )
            )

        assert updated is not None
        return updated
