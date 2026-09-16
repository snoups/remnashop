from webauthn import generate_registration_options, options_to_json
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.core.db.uow import UnitOfWork
from app.core.exceptions import AuthenticationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.passkeys.challenge_store import PasskeyChallengeStore
from app.modules.passkeys.dto import RP_NAME
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


class GetPasskeyRegistrationOptionsUseCase(UseCase[None, str]):
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

    async def _execute(self, actor: UserDto, data: None) -> str:
        async with self._uow:
            settings = await self._settings_repository.get_oauth_settings()
            if not settings.passkey_enabled:
                raise AuthenticationError("Passkeys are not enabled")
            if settings.passkey_rp_id is None or settings.passkey_origin is None:
                raise AuthenticationError("Passkeys are not configured")

            assert actor.login is not None
            existing = await self._passkey_repository.list_by_user(actor.id)

            options = generate_registration_options(
                rp_id=settings.passkey_rp_id,
                rp_name=RP_NAME,
                user_id=str(actor.id).encode(),
                user_name=actor.login,
                user_display_name=actor.name,
                authenticator_selection=AuthenticatorSelectionCriteria(
                    resident_key=ResidentKeyRequirement.PREFERRED,
                    user_verification=UserVerificationRequirement.REQUIRED,
                ),
                exclude_credentials=[
                    PublicKeyCredentialDescriptor(id=base64url_to_bytes(passkey.credential_id))
                    for passkey in existing
                ],
            )
        await self._challenge_store.store_registration_challenge(actor.id, options.challenge)
        return options_to_json(options)
