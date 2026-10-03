from typing import Final, Optional

from app.core.config import AppConfig
from app.core.constants import LOGIN_PATTERN
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.core.ports import EventPublisher
from app.core.security import verify_password
from app.modules.auth.events import LoginFailedEvent, LoginSucceededEvent
from app.modules.auth.session_issuer import IssuedSession, SessionIssuer
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto, UserRepository

# A syntactically-valid but unusable hash ("<32-hex salt>:<128-hex digest>", the
# exact shape hash_password() produces) -- verified against on an unknown login
# so scrypt always runs. Without this, a missing login returns before scrypt
# even starts, and the timing gap reveals which logins exist.
_DUMMY_PASSWORD_HASH: Final[str] = ("0" * 32) + ":" + ("0" * 128)
# Same bounds bootstrap enforces on a login. A value outside them can't belong
# to any account, and would otherwise reach the audit payload and the log raw.
_LOGIN_MAX_LENGTH: Final[int] = 64
_PASSWORD_MAX_LENGTH: Final[int] = 1024


class LoginUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        config: AppConfig,
        event_publisher: EventPublisher,
        session_issuer: SessionIssuer,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._config = config
        self._event_publisher = event_publisher
        self._session_issuer = session_issuer
        self._settings_repository = settings_repository
        self._uow = uow

    async def execute(
        self, login: str, password: str, client_ip: str, user_agent: Optional[str]
    ) -> tuple[UserDto, IssuedSession]:
        if (
            len(login) > _LOGIN_MAX_LENGTH
            or not LOGIN_PATTERN.match(login)
            or len(password) > _PASSWORD_MAX_LENGTH
        ):
            raise AuthenticationError(
                "Invalid login or password", code=ErrorCode.INVALID_CREDENTIALS
            )

        async with self._uow:
            oauth_settings = await self._settings_repository.get_oauth_settings()
            if not oauth_settings.password_login_enabled:
                raise AuthenticationError(
                    "Password login is disabled", code=ErrorCode.PASSWORD_LOGIN_DISABLED
                )

            user = await self._user_repository.get_by_login(login)
            password_pepper = self._config.crypt_key.get_secret_value()

            stored_hash = (
                user.password_hash if user and user.password_hash else _DUMMY_PASSWORD_HASH
            )
        password_is_valid = await verify_password(password, stored_hash, password_pepper)

        # Same generic error whether the login doesn't exist, the password is
        # wrong, or the account is blocked -- distinguishing any of these would
        # let a client enumerate logins or blocked-status. verify_password()
        # above always ran (even against the dummy hash), so an unknown login
        # doesn't respond measurably faster and leak via timing.
        if user is None or user.password_hash is None or not password_is_valid or user.is_blocked:
            async with self._uow:
                await self._event_publisher.publish(
                    LoginFailedEvent(login=login, ip_address=client_ip)
                )
            raise AuthenticationError(
                "Invalid login or password", code=ErrorCode.INVALID_CREDENTIALS
            )

        issued = await self._session_issuer.issue(user.id, client_ip, user_agent)
        async with self._uow:
            await self._event_publisher.publish(
                LoginSucceededEvent(user=user, ip_address=client_ip)
            )
        return user, issued
