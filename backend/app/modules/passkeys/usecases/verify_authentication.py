import json
from typing import Any, Final, Optional

from webauthn import verify_authentication_response
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.exceptions import WebAuthnException

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.core.ports import EventPublisher
from app.modules.auth import IssuedSession, SessionIssuer
from app.modules.passkeys.challenge_store import PasskeyChallengeStore
from app.modules.passkeys.events import (
    PasskeyLoginFailedEvent,
    PasskeyLoginSucceededEvent,
)
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto, UserRepository

_CREDENTIAL_ID_MAX_LENGTH: Final[int] = 255


def _read_client_data_challenge(credential: dict[str, Any]) -> Optional[str]:
    try:
        client_data_json = credential["response"]["clientDataJSON"]
        client_data = json.loads(base64url_to_bytes(client_data_json))
    except (KeyError, TypeError, ValueError):
        return None
    challenge = client_data.get("challenge")
    return challenge if isinstance(challenge, str) else None


class VerifyPasskeyAuthenticationUseCase:
    def __init__(
        self,
        settings_repository: SettingsRepository,
        passkey_repository: PasskeyRepository,
        user_repository: UserRepository,
        challenge_store: PasskeyChallengeStore,
        session_issuer: SessionIssuer,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._passkey_repository = passkey_repository
        self._user_repository = user_repository
        self._challenge_store = challenge_store
        self._session_issuer = session_issuer
        self._uow = uow
        self._event_publisher = event_publisher

    async def _fail(
        self,
        message: str,
        code: ErrorCode,
        client_ip: str,
        credential_id: Optional[str] = None,
    ) -> AuthenticationError:
        async with self._uow:
            await self._event_publisher.publish(
                PasskeyLoginFailedEvent(ip_address=client_ip, credential_id=credential_id)
            )
        return AuthenticationError(message, code=code)

    async def execute(
        self, credential: dict[str, Any], client_ip: str, user_agent: Optional[str]
    ) -> tuple[UserDto, IssuedSession]:
        async with self._uow:
            settings = await self._settings_repository.get_oauth_settings()
        if not settings.passkey_enabled:
            raise await self._fail(
                "Passkeys are not enabled", ErrorCode.PASSKEYS_DISABLED, client_ip
            )
        if settings.passkey_rp_id is None or settings.passkey_origin is None:
            raise await self._fail(
                "Passkeys are not configured", ErrorCode.PASSKEYS_NOT_CONFIGURED, client_ip
            )

        credential_id = credential.get("id")
        # the stored column is 255 wide; anything longer can't match and would
        # land in the failure event's payload as-is
        if not isinstance(credential_id, str) or len(credential_id) > _CREDENTIAL_ID_MAX_LENGTH:
            raise await self._fail(
                "Invalid passkey credential", ErrorCode.PASSKEY_INVALID, client_ip
            )

        # credential_id is a WebAuthn-generated, effectively-unguessable
        # identifier (unlike a login name), so looking it up before running
        # signature verification isn't a meaningful user-enumeration timing
        # oracle the way an unknown *login* would be in LoginUseCase.
        async with self._uow:
            stored = await self._passkey_repository.get_by_credential_id(credential_id)
        if stored is None:
            raise await self._fail(
                "Passkey not recognized", ErrorCode.PASSKEY_NOT_RECOGNIZED, client_ip, credential_id
            )

        challenge = _read_client_data_challenge(credential)
        if challenge is None or not await self._challenge_store.consume_authentication_challenge(
            challenge
        ):
            raise await self._fail(
                "Authentication challenge not found or expired",
                ErrorCode.PASSKEY_CHALLENGE_EXPIRED,
                client_ip,
                credential_id,
            )

        try:
            verification = verify_authentication_response(
                credential=credential,
                expected_challenge=base64url_to_bytes(challenge),
                expected_rp_id=settings.passkey_rp_id,
                # accepts the bare-https rp_id origin too -- admin-configured
                # passkey_origin can drift from what the browser presents
                # (trailing slash, proxy TLS termination)
                expected_origin=[settings.passkey_origin, f"https://{settings.passkey_rp_id}"],
                credential_public_key=stored.public_key,
                credential_current_sign_count=stored.sign_count,
                require_user_verification=True,
            )
        except WebAuthnException as error:
            raise await self._fail(
                "Passkey authentication could not be verified",
                ErrorCode.PASSKEY_INVALID,
                client_ip,
                credential_id,
            ) from error

        async with self._uow:
            user = await self._user_repository.get_by_id(stored.user_id)
        # Same generic message whether the user record is gone or blocked --
        # matches LoginUseCase/OAuthLoginCallbackUseCase's no-enumeration rule.
        if user is None or user.is_blocked:
            raise await self._fail(
                "Passkey not recognized", ErrorCode.PASSKEY_NOT_RECOGNIZED, client_ip, credential_id
            )

        async with self._uow:
            await self._passkey_repository.update_after_authentication(
                stored.id, verification.new_sign_count
            )
        issued = await self._session_issuer.issue(user.id, client_ip, user_agent)
        async with self._uow:
            await self._event_publisher.publish(
                PasskeyLoginSucceededEvent(
                    user=user, credential_name=stored.name, ip_address=client_ip
                )
            )
        return user, issued
