from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.core.security import hash_password, verify_password
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.users.display_name import clean_display_name
from app.modules.users.dto import UpdateOwnProfileDto, UpdateUserDto, UserDto
from app.modules.users.events import PasswordChangedEvent
from app.modules.users.ports import SessionRevoker
from app.modules.users.repository import UserRepository


class UpdateOwnProfileUseCase(UseCase[UpdateOwnProfileDto, UserDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        user_repository: UserRepository,
        uow: UnitOfWork,
        config: AppConfig,
        session_revoker: SessionRevoker,
        event_publisher: EventPublisher,
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._config = config
        self._session_revoker = session_revoker
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: UpdateOwnProfileDto) -> UserDto:
        if data.new_password is not None and not PermissionPolicy.has_permission(
            actor, Permission.OWN_ACCOUNT_MANAGE
        ):
            # customers sign in without a password; only staff manage one
            raise PermissionDeniedError("Password change is not available")

        name = None
        if data.name is not None:
            name = clean_display_name(data.name)
            if not name:
                raise ValidationError(
                    "Name must contain letters or digits", code=ErrorCode.NAME_INVALID
                )

        password_hash = None

        if data.new_password is not None:
            pepper = self._config.crypt_key.get_secret_value()
            stored_hash = actor.password_hash

            if (
                stored_hash is None
                or data.current_password is None
                or not await verify_password(data.current_password, stored_hash, pepper)
            ):
                raise ValidationError(
                    "Current password is incorrect", code=ErrorCode.CURRENT_PASSWORD_INCORRECT
                )

            password_hash = await hash_password(data.new_password, pepper)

        async with self._uow:
            updated = await self._user_repository.update_fields(
                actor.id,
                UpdateUserDto(
                    name=name,
                    password_hash=password_hash,
                    password_change_required=False if password_hash is not None else None,
                    language=data.language,
                ),
            )
            if password_hash is not None:
                # a password change may mean a compromise, so every other
                # session ends now (UpdateAdminUseCase does the same on revokes)
                await self._session_revoker.revoke_all_by_user(
                    actor.id, keep_session_id=data.current_session_id
                )
                await self._event_publisher.publish(
                    PasswordChangedEvent(user=actor, ip_address=data.client_ip)
                )

        assert updated is not None
        return updated
