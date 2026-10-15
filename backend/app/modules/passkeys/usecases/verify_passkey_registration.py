from webauthn import verify_registration_response
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import WebAuthnException

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.passkeys.challenge_store import PasskeyChallengeStore
from app.modules.passkeys.dto import (
    PASSKEY_CREDENTIAL_ID_MAX_LENGTH,
    CreatePasskeyCredentialDto,
    PasskeyCredentialDto,
    VerifyPasskeyRegistrationDto,
)
from app.modules.passkeys.events import PasskeyRegisteredEvent
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


class VerifyPasskeyRegistrationUseCase(
    UseCase[VerifyPasskeyRegistrationDto, PasskeyCredentialDto, UserDto]
):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        passkey_repository: PasskeyRepository,
        challenge_store: PasskeyChallengeStore,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._passkey_repository = passkey_repository
        self._challenge_store = challenge_store
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(
        self, actor: UserDto, data: VerifyPasskeyRegistrationDto
    ) -> PasskeyCredentialDto:
        async with self._uow:
            settings = await self._settings_repository.get_oauth_settings()
            if not settings.passkey_enabled:
                raise AuthenticationError(
                    "Passkeys are not enabled", code=ErrorCode.PASSKEYS_DISABLED
                )
            if settings.passkey_rp_id is None or settings.passkey_origin is None:
                raise AuthenticationError(
                    "Passkeys are not configured", code=ErrorCode.PASSKEYS_NOT_CONFIGURED
                )

        challenge = await self._challenge_store.consume_registration_challenge(actor.id)
        if challenge is None:
            raise AuthenticationError(
                "Registration challenge not found or expired",
                code=ErrorCode.PASSKEY_CHALLENGE_EXPIRED,
            )

        try:
            verification = verify_registration_response(
                credential=data.credential,
                expected_challenge=challenge,
                expected_rp_id=settings.passkey_rp_id,
                # the bare-https rp_id origin too: the configured passkey_origin
                # can differ from what the browser sends (trailing slash, TLS
                # terminated at a proxy)
                expected_origin=[settings.passkey_origin, f"https://{settings.passkey_rp_id}"],
                require_user_verification=True,
            )
        except WebAuthnException as error:
            raise AuthenticationError(
                "Passkey registration could not be verified",
                code=ErrorCode.PASSKEY_REGISTRATION_FAILED,
            ) from error

        credential_id = bytes_to_base64url(verification.credential_id)
        # the column is that wide; a longer id would be a 500 on insert
        if len(credential_id) > PASSKEY_CREDENTIAL_ID_MAX_LENGTH:
            raise AuthenticationError(
                "Passkey credential id is too long", code=ErrorCode.PASSKEY_REGISTRATION_FAILED
            )

        transports = data.credential.get("response", {}).get("transports")

        async with self._uow:
            credential = await self._passkey_repository.create(
                CreatePasskeyCredentialDto(
                    user_id=actor.id,
                    credential_id=credential_id,
                    public_key=verification.credential_public_key,
                    sign_count=verification.sign_count,
                    transports=transports,
                    device_type=verification.credential_device_type.value,
                    backed_up=verification.credential_backed_up,
                    name=data.name or "Passkey",
                )
            )
            await self._event_publisher.publish(
                PasskeyRegisteredEvent(
                    user=actor, credential_name=credential.name, ip_address=data.client_ip
                )
            )
        return credential
