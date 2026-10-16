from types import SimpleNamespace
from typing import Any

import pytest
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.ports import EventPublisher
from app.modules.auth import SessionIssuer
from app.modules.passkeys.challenge_store import PasskeyChallengeStore
from app.modules.passkeys.dto import (
    CreatePasskeyCredentialDto,
    DeletePasskeyDto,
    RenamePasskeyDto,
    VerifyPasskeyRegistrationDto,
)
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.passkeys.usecases import (
    DeletePasskeyUseCase,
    GetPasskeyAuthenticationOptionsUseCase,
    GetPasskeyRegistrationOptionsUseCase,
    ListPasskeysUseCase,
    RenamePasskeyUseCase,
    VerifyPasskeyAuthenticationUseCase,
    VerifyPasskeyRegistrationUseCase,
    verify_passkey_registration,
)
from app.modules.settings.dto import UpdateOAuthSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.events import RecordingEventPublisher

RP_ID = "example.com"
ORIGIN = "https://example.com"


async def _create_user(
    user_repository: UserRepository, uow: UnitOfWork, login: str, role: Role = Role.OWNER
) -> UserDto:
    # OWNER is unique (partial index), so a second user needs role=Role.ADMIN;
    # USER would lack Permission.OWN_ACCOUNT_MANAGE.
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login=login, name=login, role=role, language=Locale.EN)
        )
        await uow.commit()
    return user


async def _enable_passkeys(settings_repository: SettingsRepository) -> None:
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(passkey_enabled=True, passkey_rp_id=RP_ID, passkey_origin=ORIGIN)
    )


def _fake_registration_credential(challenge: bytes) -> dict[str, Any]:
    # a correctly signed response needs a real WebAuthn client, so these tests
    # cover the error paths with a deliberately invalid credential; a real
    # browser response is checked by hand
    return {
        "id": "not-a-real-credential",
        "rawId": bytes_to_base64url(b"not-a-real-credential"),
        "response": {
            "attestationObject": bytes_to_base64url(b"invalid"),
            "clientDataJSON": bytes_to_base64url(
                (
                    '{"type":"webauthn.create","challenge":"'
                    + bytes_to_base64url(challenge)
                    + '","origin":"'
                    + ORIGIN
                    + '"}'
                ).encode()
            ),
            "transports": ["internal"],
        },
        "type": "public-key",
        "clientExtensionResults": {},
    }


async def test_get_registration_options_rejects_when_disabled(
    settings_repository: SettingsRepository,
    passkey_repository: PasskeyRepository,
    redis_challenge_store: PasskeyChallengeStore,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    actor = await _create_user(user_repository, uow, "owner")
    use_case = GetPasskeyRegistrationOptionsUseCase(
        settings_repository, passkey_repository, redis_challenge_store, uow
    )

    with pytest.raises(AuthenticationError):
        await use_case(actor)


async def test_get_registration_options_returns_json_when_enabled(
    settings_repository: SettingsRepository,
    passkey_repository: PasskeyRepository,
    redis_challenge_store: PasskeyChallengeStore,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    actor = await _create_user(user_repository, uow, "owner")
    await _enable_passkeys(settings_repository)
    use_case = GetPasskeyRegistrationOptionsUseCase(
        settings_repository, passkey_repository, redis_challenge_store, uow
    )

    options_json = await use_case(actor)

    assert '"rp"' in options_json
    assert RP_ID in options_json


async def test_verify_registration_rejects_expired_challenge(
    settings_repository: SettingsRepository,
    passkey_repository: PasskeyRepository,
    redis_challenge_store: PasskeyChallengeStore,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    actor = await _create_user(user_repository, uow, "owner")
    await _enable_passkeys(settings_repository)
    use_case = VerifyPasskeyRegistrationUseCase(
        settings_repository, passkey_repository, redis_challenge_store, uow, event_publisher
    )

    credential = _fake_registration_credential(b"some-challenge")
    with pytest.raises(AuthenticationError, match="challenge"):
        await use_case(
            actor,
            VerifyPasskeyRegistrationDto(credential=credential, name=None, client_ip="127.0.0.1"),
        )


async def test_verify_registration_rejects_invalid_response(
    settings_repository: SettingsRepository,
    passkey_repository: PasskeyRepository,
    redis_challenge_store: PasskeyChallengeStore,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    actor = await _create_user(user_repository, uow, "owner")
    await _enable_passkeys(settings_repository)
    challenge = b"a-real-looking-challenge"
    await redis_challenge_store.store_registration_challenge(actor.id, challenge)

    use_case = VerifyPasskeyRegistrationUseCase(
        settings_repository, passkey_repository, redis_challenge_store, uow, event_publisher
    )
    credential = _fake_registration_credential(challenge)

    with pytest.raises(AuthenticationError, match="verified"):
        await use_case(
            actor,
            VerifyPasskeyRegistrationDto(credential=credential, name=None, client_ip="127.0.0.1"),
        )

    # a failed verification still consumes the challenge, so a second attempt
    # fails as "expired"
    with pytest.raises(AuthenticationError, match="challenge"):
        await use_case(
            actor,
            VerifyPasskeyRegistrationDto(credential=credential, name=None, client_ip="127.0.0.1"),
        )


def _create_passkey_dto(user_id: int, credential_id: str = "cred-1") -> CreatePasskeyCredentialDto:
    return CreatePasskeyCredentialDto(
        user_id=user_id,
        credential_id=credential_id,
        public_key=b"pubkey",
        sign_count=0,
        transports=None,
        device_type="single_device",
        backed_up=False,
        name="My laptop",
    )


async def test_list_passkeys_returns_only_actors_own(
    passkey_repository: PasskeyRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    actor = await _create_user(user_repository, uow, "owner")
    other = await _create_user(user_repository, uow, "other", role=Role.ADMIN)
    await passkey_repository.create(_create_passkey_dto(actor.id, "cred-actor"))
    await passkey_repository.create(_create_passkey_dto(other.id, "cred-other"))

    use_case = ListPasskeysUseCase(passkey_repository, uow)
    result = await use_case(actor)

    assert len(result) == 1
    assert result[0].credential_id == "cred-actor"


async def test_rename_passkey_updates_name(
    passkey_repository: PasskeyRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    actor = await _create_user(user_repository, uow, "owner")
    created = await passkey_repository.create(_create_passkey_dto(actor.id))

    publisher = RecordingEventPublisher()
    use_case = RenamePasskeyUseCase(passkey_repository, uow, publisher)
    renamed = await use_case(actor, RenamePasskeyDto(id=created.id, name="New name"))

    assert renamed.name == "New name"
    assert [e.credential_name for e in publisher.events] == ["New name"]  # type: ignore[attr-defined]


async def test_rename_passkey_rejects_other_users_passkey(
    passkey_repository: PasskeyRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    owner = await _create_user(user_repository, uow, "owner")
    other = await _create_user(user_repository, uow, "other", role=Role.ADMIN)
    created = await passkey_repository.create(_create_passkey_dto(owner.id))

    use_case = RenamePasskeyUseCase(passkey_repository, uow, RecordingEventPublisher())
    with pytest.raises(NotFoundError):
        await use_case(other, RenamePasskeyDto(id=created.id, name="Hijacked"))


async def test_delete_passkey_removes_it(
    passkey_repository: PasskeyRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    actor = await _create_user(user_repository, uow, "owner")
    created = await passkey_repository.create(_create_passkey_dto(actor.id))

    use_case = DeletePasskeyUseCase(passkey_repository, uow, event_publisher)
    await use_case(actor, DeletePasskeyDto(passkey_id=created.id, client_ip="127.0.0.1"))

    assert await passkey_repository.get_by_id_and_user(created.id, actor.id) is None


async def test_delete_passkey_rejects_other_users_passkey(
    passkey_repository: PasskeyRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    owner = await _create_user(user_repository, uow, "owner")
    other = await _create_user(user_repository, uow, "other", role=Role.ADMIN)
    created = await passkey_repository.create(_create_passkey_dto(owner.id))

    use_case = DeletePasskeyUseCase(passkey_repository, uow, event_publisher)
    with pytest.raises(NotFoundError):
        await use_case(other, DeletePasskeyDto(passkey_id=created.id, client_ip="127.0.0.1"))


CLIENT_IP = "203.0.113.1"
USER_AGENT = "pytest"


async def test_get_authentication_options_rejects_when_disabled(
    settings_repository: SettingsRepository,
    redis_challenge_store: PasskeyChallengeStore,
    uow: UnitOfWork,
) -> None:
    use_case = GetPasskeyAuthenticationOptionsUseCase(
        settings_repository, redis_challenge_store, uow
    )
    with pytest.raises(AuthenticationError):
        await use_case.execute()


async def test_get_authentication_options_returns_json_when_enabled(
    settings_repository: SettingsRepository,
    redis_challenge_store: PasskeyChallengeStore,
    uow: UnitOfWork,
) -> None:
    await _enable_passkeys(settings_repository)
    use_case = GetPasskeyAuthenticationOptionsUseCase(
        settings_repository, redis_challenge_store, uow
    )

    options_json = await use_case.execute()
    assert RP_ID in options_json


async def test_verify_authentication_rejects_unknown_credential_id(
    settings_repository: SettingsRepository,
    passkey_repository: PasskeyRepository,
    user_repository: UserRepository,
    redis_challenge_store: PasskeyChallengeStore,
    uow: UnitOfWork,
    session_repository,
    config,
    event_publisher: EventPublisher,
) -> None:
    await _enable_passkeys(settings_repository)
    session_issuer = SessionIssuer(session_repository, uow, config)
    use_case = VerifyPasskeyAuthenticationUseCase(
        settings_repository,
        passkey_repository,
        user_repository,
        redis_challenge_store,
        session_issuer,
        uow,
        event_publisher,
    )

    credential = {
        "id": "unknown-credential",
        "rawId": bytes_to_base64url(b"unknown-credential"),
        "response": {
            "authenticatorData": bytes_to_base64url(b"auth-data"),
            "clientDataJSON": bytes_to_base64url(
                b'{"type":"webauthn.get","challenge":"xyz","origin":"' + ORIGIN.encode() + b'"}'
            ),
            "signature": bytes_to_base64url(b"sig"),
        },
        "type": "public-key",
        "clientExtensionResults": {},
    }

    with pytest.raises(AuthenticationError, match="not recognized"):
        await use_case.execute(credential, CLIENT_IP, USER_AGENT)


async def test_verify_authentication_rejects_unknown_challenge(
    settings_repository: SettingsRepository,
    passkey_repository: PasskeyRepository,
    user_repository: UserRepository,
    redis_challenge_store: PasskeyChallengeStore,
    uow: UnitOfWork,
    session_repository,
    config,
    event_publisher: EventPublisher,
) -> None:
    await _enable_passkeys(settings_repository)
    actor = await _create_user(user_repository, uow, "owner")
    created = await passkey_repository.create(_create_passkey_dto(actor.id, "known-credential"))

    session_issuer = SessionIssuer(session_repository, uow, config)
    use_case = VerifyPasskeyAuthenticationUseCase(
        settings_repository,
        passkey_repository,
        user_repository,
        redis_challenge_store,
        session_issuer,
        uow,
        event_publisher,
    )

    credential = {
        "id": created.credential_id,
        "rawId": bytes_to_base64url(base64url_to_bytes(created.credential_id)),
        "response": {
            "authenticatorData": bytes_to_base64url(b"auth-data"),
            "clientDataJSON": bytes_to_base64url(
                b'{"type":"webauthn.get","challenge":"never-stored","origin":"'
                + ORIGIN.encode()
                + b'"}'
            ),
            "signature": bytes_to_base64url(b"sig"),
        },
        "type": "public-key",
        "clientExtensionResults": {},
    }

    with pytest.raises(AuthenticationError, match="[Cc]hallenge"):
        await use_case.execute(credential, CLIENT_IP, USER_AGENT)


async def test_verify_authentication_rejects_malformed_credential_structure(
    settings_repository: SettingsRepository,
    passkey_repository: PasskeyRepository,
    user_repository: UserRepository,
    redis_challenge_store: PasskeyChallengeStore,
    uow: UnitOfWork,
    session_repository,
    config,
    event_publisher: EventPublisher,
) -> None:
    await _enable_passkeys(settings_repository)
    actor = await _create_user(user_repository, uow, "owner")
    created = await passkey_repository.create(_create_passkey_dto(actor.id, "known-credential"))

    challenge = bytes_to_base64url(b"a-real-challenge")
    await redis_challenge_store.store_authentication_challenge(challenge)

    session_issuer = SessionIssuer(session_repository, uow, config)
    use_case = VerifyPasskeyAuthenticationUseCase(
        settings_repository,
        passkey_repository,
        user_repository,
        redis_challenge_store,
        session_issuer,
        uow,
        event_publisher,
    )

    # without rawId parse_authentication_credential_json raises
    # InvalidJSONStructure, which the usecase must catch too
    credential = {
        "id": created.credential_id,
        "response": {
            "authenticatorData": bytes_to_base64url(b"auth-data"),
            "clientDataJSON": bytes_to_base64url(
                b'{"type":"webauthn.get","challenge":"'
                + challenge.encode()
                + b'","origin":"'
                + ORIGIN.encode()
                + b'"}'
            ),
            "signature": bytes_to_base64url(b"sig"),
        },
        "type": "public-key",
        "clientExtensionResults": {},
    }

    with pytest.raises(AuthenticationError):
        await use_case.execute(credential, CLIENT_IP, USER_AGENT)


async def test_verify_registration_rejects_an_oversized_credential_id(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    passkey_repository: PasskeyRepository,
    redis_challenge_store: PasskeyChallengeStore,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    actor = await _create_user(user_repository, uow, "owner")
    await _enable_passkeys(settings_repository)
    challenge = b"a-real-looking-challenge"
    await redis_challenge_store.store_registration_challenge(actor.id, challenge)
    monkeypatch.setattr(
        verify_passkey_registration,
        "verify_registration_response",
        lambda **_: SimpleNamespace(
            credential_id=b"x" * 300,
            credential_public_key=b"key",
            sign_count=0,
            credential_device_type=SimpleNamespace(value="single_device"),
            credential_backed_up=False,
        ),
    )
    use_case = VerifyPasskeyRegistrationUseCase(
        settings_repository, passkey_repository, redis_challenge_store, uow, event_publisher
    )

    with pytest.raises(AuthenticationError) as error:
        await use_case(
            actor,
            VerifyPasskeyRegistrationDto(
                credential=_fake_registration_credential(challenge),
                name=None,
                client_ip="127.0.0.1",
            ),
        )

    assert error.value.code is ErrorCode.PASSKEY_REGISTRATION_FAILED
