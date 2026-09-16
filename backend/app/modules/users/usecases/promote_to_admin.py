from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.exc import IntegrityError

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.ports import EventPublisher
from app.core.security import generate_password, hash_password
from app.core.security.permissions import Permission, assert_grantable
from app.core.usecase import UseCase
from app.modules.users.dto import PromoteAdminDto, UserDto
from app.modules.users.events import AdminPromotedEvent
from app.modules.users.repository import UserRepository


@dataclass(frozen=True, kw_only=True)
class PromoteToAdminDto:
    client_ip: str
    email: Optional[str] = None
    telegram_username: Optional[str] = None
    login: Optional[str] = None
    permission_grants: list[Permission] = field(default_factory=list)
    permission_revokes: list[Permission] = field(default_factory=list)


class PromoteToAdminUseCase(UseCase[PromoteToAdminDto, tuple[UserDto, Optional[str]]]):
    required_permission = Permission.ADMINS_MANAGE

    def __init__(
        self,
        user_repository: UserRepository,
        uow: UnitOfWork,
        config: AppConfig,
        event_publisher: EventPublisher,
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._config = config
        self._event_publisher = event_publisher

    async def _execute(
        self, actor: UserDto, data: PromoteToAdminDto
    ) -> tuple[UserDto, Optional[str]]:
        async with self._uow:
            assert_grantable(data.permission_grants)

            target = None
            if data.email:
                target = await self._user_repository.get_by_email(data.email)
            elif data.telegram_username:
                target = await self._user_repository.get_by_username(data.telegram_username)

            if target is None:
                raise NotFoundError("User not found")
            if target.role != Role.USER:
                raise ConflictError("User is already privileged")

            login = target.login or data.login
            if login is None:
                raise ValidationError("login is required to promote a user without one")

            existing_password_hash = target.password_hash
            password: Optional[str] = None
        if existing_password_hash is None:
            password = generate_password()
            password_hash = await hash_password(password, self._config.crypt_key.get_secret_value())
        else:
            password_hash = existing_password_hash

        try:
            async with self._uow:
                updated = await self._user_repository.promote_to_admin(
                    target.id,
                    PromoteAdminDto(
                        login=login,
                        password_hash=password_hash,
                        permission_grants=[p.value for p in data.permission_grants],
                        permission_revokes=[p.value for p in data.permission_revokes],
                    ),
                )
                assert updated is not None
                await self._event_publisher.publish(
                    AdminPromotedEvent(actor=actor, target=updated, ip_address=data.client_ip)
                )
        except IntegrityError as error:
            raise ConflictError("Login already taken") from error

        return updated, password
