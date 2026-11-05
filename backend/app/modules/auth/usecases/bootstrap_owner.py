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
from app.modules.settings import SettingsRepository
from app.modules.users import CreateUserDto, UserDto, UserRepository


class BootstrapOwnerUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        config: AppConfig,
        event_publisher: EventPublisher,
        session_issuer: SessionIssuer,
    ) -> None:
        self._user_repository = user_repository
        self._settings_repository = settings_repository
        self._uow = uow
        self._config = config
        self._event_publisher = event_publisher
        self._session_issuer = session_issuer

    async def execute(
        self, login: str, password: str, client_ip: str, user_agent: Optional[str]
    ) -> tuple[UserDto, IssuedSession]:
        async with self._uow:
            settings = await self._settings_repository.get_oauth_settings()
            owner_exists = await self._user_repository.exists_with_role(Role.OWNER)
        claim_pending = settings.owner_claim_pending
        if owner_exists and not claim_pending:
            async with self._uow:
                await self._event_publisher.publish(
                    BootstrapConflictEvent(login=login, ip_address=client_ip)
                )
            raise ConflictError("Owner already exists", code=ErrorCode.OWNER_ALREADY_EXISTS)

        password_pepper = self._config.crypt_key.get_secret_value()
        password_hash = await hash_password(password, password_pepper)

        # A concurrent bootstrap can slip past the checks above; the partial
        # unique index ux_users_single_owner rejects its write, and the
        # repository turns that into the same OWNER_ALREADY_EXISTS conflict.
        async with self._uow:
            owner = None
            if claim_pending:
                owner = await self._claim_migrated_owner(login, password_hash)
            if owner is None:
                owner = await self._user_repository.create(
                    CreateUserDto(
                        login=login,
                        password_hash=password_hash,
                        name=login,
                        role=Role.OWNER,
                        language=Locale.EN,
                    )
                )
            await self._event_publisher.publish(
                OwnerBootstrappedEvent(user=owner, ip_address=client_ip)
            )

        issued = await self._session_issuer.issue(owner.id, client_ip, user_agent)
        return owner, issued

    async def _claim_migrated_owner(self, login: str, password_hash: str) -> Optional[UserDto]:
        # re-read under the lock: of two concurrent claims only the first sees it set,
        # the other falls through to create() and hits the single-owner index
        settings = await self._settings_repository.lock_oauth_settings(exclusive=True)
        if not settings.owner_claim_pending:
            return None
        await self._settings_repository.clear_owner_claim()
        return await self._user_repository.claim_owner(login, password_hash)
