from typing import Optional

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.security import hash_password
from app.modules.auth.events import BootstrapConflictEvent, OwnerBootstrappedEvent
from app.modules.auth.session_issuer import IssuedSession, SessionIssuer
from app.modules.users import CreateUserDto, UserDto, UserRepository


class BootstrapOwnerUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        uow: UnitOfWork,
        config: AppConfig,
        event_publisher: EventPublisher,
        session_issuer: SessionIssuer,
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._config = config
        self._event_publisher = event_publisher
        self._session_issuer = session_issuer

    async def execute(
        self, login: str, password: str, client_ip: str, user_agent: Optional[str]
    ) -> tuple[UserDto, IssuedSession]:
        async with self._uow:
            owner_exists = await self._user_repository.exists_with_role(Role.OWNER)
        if owner_exists:
            async with self._uow:
                await self._event_publisher.publish(
                    BootstrapConflictEvent(login=login, ip_address=client_ip)
                )
            raise ConflictError("Owner already exists", code=ErrorCode.OWNER_ALREADY_EXISTS)

        password_pepper = self._config.crypt_key.get_secret_value()
        password_hash = await hash_password(password, password_pepper)

        # A concurrent bootstrap can slip past exists_with_role() above; the
        # partial unique index ux_users_single_owner rejects its write, and the
        # repository turns that into the same OWNER_ALREADY_EXISTS conflict.
        async with self._uow:
            owner = await self._user_repository.create(
                CreateUserDto(
                    login=login,
                    password_hash=password_hash,
                    name=login,
                    role=Role.OWNER,
                    language=Locale.EN,
                )
            )

        issued = await self._session_issuer.issue(owner.id, client_ip, user_agent)
        async with self._uow:
            await self._event_publisher.publish(
                OwnerBootstrappedEvent(user=owner, ip_address=client_ip)
            )
        return owner, issued
