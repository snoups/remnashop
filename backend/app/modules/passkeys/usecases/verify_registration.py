from webauthn import verify_registration_response
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import WebAuthnException

from app.core.db.uow import UnitOfWork
from app.core.exceptions import AuthenticationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.passkeys.challenge_store import PasskeyChallengeStore
from app.modules.passkeys.dto import (
    CreatePasskeyCredentialDto,
    PasskeyCredentialDto,
    VerifyPasskeyRegistrationDto,
)
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


class VerifyPasskeyRegistrationUseCase(UseCase[VerifyPasskeyRegistrationDto, PasskeyCredentialDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        passkey_repository: PasskeyRepository,
        challenge_store: PasskeyChallengeStore,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._passkey_repository = passkey_repository
        self._challenge_store = challenge_store
        self._uow = uow

    async def _execute(
        self, actor: UserDto, data: VerifyPasskeyRegistrationDto
    ) -> PasskeyCredentialDto:
        settings = await self._settings_repository.get_oauth_settings()
        if not settings.passkey_enabled:
            raise AuthenticationError("Passkeys are not enabled")
        if settings.passkey_rp_id is None or settings.passkey_origin is None:
            raise AuthenticationError("Passkeys are not configured")

        challenge = await self._challenge_store.consume_registration_challenge(actor.id)
        if challenge is None:
            raise AuthenticationError("Registration challenge not found or expired")

        try:
            verification = verify_registration_response(
                credential=data.credential,
                expected_challenge=challenge,
                expected_rp_id=settings.passkey_rp_id,
                # accepts the bare-https rp_id origin too -- admin-configured
                # passkey_origin can drift from what the browser presents
                # (trailing slash, proxy TLS termination); mirrors the
                # Remnawave reference this design was based on.
                expected_origin=[settings.passkey_origin, f"https://{settings.passkey_rp_id}"],
                require_user_verification=True,
            )
        except WebAuthnException as error:
            raise AuthenticationError("Passkey registration could not be verified") from error

        transports = data.credential.get("response", {}).get("transports")

        async with self._uow:
            return await self._passkey_repository.create(
                CreatePasskeyCredentialDto(
                    user_id=actor.id,
                    credential_id=bytes_to_base64url(verification.credential_id),
                    public_key=verification.credential_public_key,
                    sign_count=verification.sign_count,
                    transports=transports,
                    device_type=verification.credential_device_type.value,
                    backed_up=verification.credential_backed_up,
                    name=data.name or "Passkey",
                )
            )
