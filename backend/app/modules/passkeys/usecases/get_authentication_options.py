from webauthn import generate_authentication_options, options_to_json
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.structs import UserVerificationRequirement

from app.core.db.uow import UnitOfWork
from app.core.exceptions import AuthenticationError
from app.modules.passkeys.challenge_store import PasskeyChallengeStore
from app.modules.settings import SettingsRepository


class GetPasskeyAuthenticationOptionsUseCase:
    def __init__(
        self,
        settings_repository: SettingsRepository,
        challenge_store: PasskeyChallengeStore,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._challenge_store = challenge_store
        self._uow = uow

    async def execute(self) -> str:
        async with self._uow:
            settings = await self._settings_repository.get_oauth_settings()
            if not settings.passkey_enabled:
                raise AuthenticationError("Passkeys are not enabled")
            if settings.passkey_rp_id is None or settings.passkey_origin is None:
                raise AuthenticationError("Passkeys are not configured")

            # No allow_credentials -- a discoverable/usernameless ceremony, so the
            # browser's own passkey picker resolves which credential (and
            # therefore which user) is used, not a username typed up front.
            options = generate_authentication_options(
                rp_id=settings.passkey_rp_id,
                user_verification=UserVerificationRequirement.REQUIRED,
            )
        await self._challenge_store.store_authentication_challenge(
            bytes_to_base64url(options.challenge)
        )
        return options_to_json(options)
