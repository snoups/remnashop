from dataclasses import dataclass
from typing import Optional

from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ports import EventPublisher, SessionRevoker
from app.core.security.permissions import Permission, assert_grantable
from app.core.usecase import UseCase
from app.modules.users.dto import UpdateUserDto, UserDto
from app.modules.users.events import AdminPermissionsUpdatedEvent
from app.modules.users.repository import UserRepository


@dataclass(frozen=True, kw_only=True)
class UpdateAdminDto:
    user_id: int
    client_ip: str
    # None means "field omitted, leave unchanged"; an explicit [] clears the overrides.
    permission_grants: Optional[list[Permission]] = None
    permission_revokes: Optional[list[Permission]] = None


class UpdateAdminUseCase(UseCase[UpdateAdminDto, UserDto]):
    required_permission = Permission.ADMINS_MANAGE

    def __init__(
        self,
        user_repository: UserRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        session_revoker: SessionRevoker,
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._session_revoker = session_revoker

    async def _execute(self, actor: UserDto, data: UpdateAdminDto) -> UserDto:
        async with self._uow:
            if data.permission_grants is not None:
                assert_grantable(data.permission_grants)

            target = await self._user_repository.get_by_id(data.user_id)
            if target is None:
                raise NotFoundError("Admin not found")
            if target.role != Role.ADMIN:
                raise ConflictError("Target is not a manageable admin")

            update_data = UpdateUserDto(
                permission_grants=(
                    [p.value for p in data.permission_grants]
                    if data.permission_grants is not None
                    else None
                ),
                permission_revokes=(
                    [p.value for p in data.permission_revokes]
                    if data.permission_revokes is not None
                    else None
                ),
            )

        async with self._uow:
            updated = await self._user_repository.update_fields(data.user_id, update_data)
            assert updated is not None
            if data.permission_revokes is not None:
                await self._session_revoker.revoke_all_by_user(target.id)
            await self._event_publisher.publish(
                AdminPermissionsUpdatedEvent(
                    actor=actor,
                    target=updated,
                    permission_grants=update_data.permission_grants,
                    permission_revokes=update_data.permission_revokes,
                    ip_address=data.client_ip,
                )
            )
        return updated
