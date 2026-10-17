from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission, assert_grantable
from app.core.usecase import UseCase
from app.modules.users.dto import UpdateAdminDto, UpdateUserDto, UserDto
from app.modules.users.events import AdminPermissionsUpdatedEvent
from app.modules.users.ports import SessionRevoker
from app.modules.users.repository import UserRepository


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

    async def _execute(self, actor: Actor, data: UpdateAdminDto) -> UserDto:
        async with self._uow:
            if data.permission_grants is not None:
                assert_grantable(data.permission_grants)
            if data.permission_revokes is not None:
                assert_grantable(data.permission_revokes)

            target = await self._user_repository.find_live_for_update(data.user_id)
            if target is None:
                raise NotFoundError("Admin not found", code=ErrorCode.ADMIN_NOT_FOUND)
            if target.role != Role.ADMIN:
                raise ConflictError(
                    "Target is not a manageable admin", code=ErrorCode.ADMIN_NOT_MANAGEABLE
                )

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
