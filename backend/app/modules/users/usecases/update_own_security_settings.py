from dataclasses import dataclass

from app.core.db.uow import UnitOfWork
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.http import is_ip_allowed
from app.modules.users.dto import UpdateUserDto, UserDto
from app.modules.users.repository import UserRepository


@dataclass(frozen=True, kw_only=True)
class UpdateSecuritySettingsDto:
    ip_allowlist: list[str]
    client_ip: str


class UpdateOwnSecuritySettingsUseCase(UseCase[UpdateSecuritySettingsDto, UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, user_repository: UserRepository, uow: UnitOfWork) -> None:
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: UpdateSecuritySettingsDto) -> UserDto:
        if data.ip_allowlist and not is_ip_allowed(data.client_ip, data.ip_allowlist):
            raise ValidationError(
                "Your current IP is not in the submitted allowlist -- this would lock you out"
            )

        async with self._uow:
            updated = await self._user_repository.update_fields(
                actor.id, UpdateUserDto(ip_allowlist=list(data.ip_allowlist))
            )

        assert updated is not None
        return updated
