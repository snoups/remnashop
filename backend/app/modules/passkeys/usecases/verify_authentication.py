import json
from typing import Any, Optional

from webauthn import verify_authentication_response
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.exceptions import WebAuthnException

from app.core.exceptions import AuthenticationError
from app.modules.auth import IssuedSession, SessionIssuer
from app.modules.passkeys.challenge_store import PasskeyChallengeStore
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto, UserRepository


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
    ) -> None:
        self._settings_repository = settings_repository
        self._passkey_repository = passkey_repository
        self._user_repository = user_repository
        self._challenge_store = challenge_store
        self._session_issuer = session_issuer

    async def execute(
        self, credential: dict[str, Any], client_ip: str, user_agent: Optional[str]
    ) -> tuple[UserDto, IssuedSession]:
        settings = await self._settings_repository.get_oauth_settings()
        if not settings.passkey_enabled:
            raise AuthenticationError("Passkeys are not enabled")
        if settings.passkey_rp_id is None or settings.passkey_origin is None:
            raise AuthenticationError("Passkeys are not configured")

        credential_id = credential.get("id")
        if not isinstance(credential_id, str):
            raise AuthenticationError("Invalid passkey credential")

        # credential_id is a WebAuthn-generated, effectively-unguessable
        # identifier (unlike a login name), so looking it up before running
        # signature verification isn't a meaningful user-enumeration timing
        # oracle the way an unknown *login* would be in LoginUseCase.
        stored = await self._passkey_repository.get_by_credential_id(credential_id)
        if stored is None:
            raise AuthenticationError("Passkey not recognized")

        challenge = _read_client_data_challenge(credential)
        if challenge is None or not await self._challenge_store.consume_authentication_challenge(
            challenge
        ):
            raise AuthenticationError("Authentication challenge not found or expired")

        try:
            verification = verify_authentication_response(
                credential=credential,
                expected_challenge=base64url_to_bytes(challenge),
                expected_rp_id=settings.passkey_rp_id,
                # accepts the bare-https rp_id origin too -- admin-configured
                # passkey_origin can drift from what the browser presents
                # (trailing slash, proxy TLS termination); mirrors the
                # Remnawave reference this design was based on.
                expected_origin=[settings.passkey_origin, f"https://{settings.passkey_rp_id}"],
                credential_public_key=stored.public_key,
                credential_current_sign_count=stored.sign_count,
                require_user_verification=True,
            )
        except WebAuthnException as error:
            raise AuthenticationError("Passkey authentication could not be verified") from error

        user = await self._user_repository.get_by_id(stored.user_id)
        # Same generic message whether the user record is gone or blocked --
        # matches LoginUseCase/OAuthLoginCallbackUseCase's no-enumeration rule.
        if user is None or user.is_blocked:
            raise AuthenticationError("Passkey not recognized")

        await self._passkey_repository.update_after_authentication(
            stored.id, verification.new_sign_count
        )
        issued = await self._session_issuer.issue(user.id, client_ip, user_agent)
        return user, issued
