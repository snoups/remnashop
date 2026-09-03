from typing import Optional

from sqlalchemy.exc import IntegrityError

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
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
        if await self._user_repository.exists_with_role(Role.OWNER):
            async with self._uow:
                await self._event_publisher.publish(
                    BootstrapConflictEvent(login=login, ip_address=client_ip)
                )
            raise ConflictError("Owner already exists")

        password_pepper = self._config.crypt_key.get_secret_value()
        password_hash = await hash_password(password, password_pepper)

        try:
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
        except IntegrityError as error:
            # Closes the TOCTOU window on the exists_with_role() check above: a concurrent
            # bootstrap request can still slip past it, but the DB-level partial unique
            # index (ux_users_single_owner) always catches the second write.
            raise ConflictError("Owner already exists") from error

        issued = await self._session_issuer.issue(owner.id, client_ip, user_agent)
        # A failure here surfaces as a request failure by design -- durable
        # delivery means this write can't be silently swallowed.
        async with self._uow:
            await self._event_publisher.publish(
                OwnerBootstrappedEvent(user=owner, ip_address=client_ip)
            )
        return owner, issued
