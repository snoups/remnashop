from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.modules.passkeys.dto import CreatePasskeyCredentialDto
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository


async def _create_user(
    user_repository: UserRepository, uow: UnitOfWork, login: str, role: Role = Role.USER
) -> UserDto:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login=login, name=login, role=role, language=Locale.EN)
        )
        await uow.commit()
    return user


def _create_dto(user_id: int, credential_id: str = "cred-1") -> CreatePasskeyCredentialDto:
    return CreatePasskeyCredentialDto(
        user_id=user_id,
        credential_id=credential_id,
        public_key=b"pubkey",
        sign_count=0,
        transports=["internal"],
        device_type="single_device",
        backed_up=False,
        name="My laptop",
    )


async def test_create_then_get_by_credential_id(
    passkey_repository: PasskeyRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner", role=Role.OWNER)

    created = await passkey_repository.create(_create_dto(user.id))
    assert created.credential_id == "cred-1"

    found = await passkey_repository.find_by_credential_id("cred-1")
    assert found is not None
    assert found.user_id == user.id
    assert found.public_key == b"pubkey"


async def test_get_by_credential_id_returns_none_when_missing(
    passkey_repository: PasskeyRepository,
) -> None:
    assert await passkey_repository.find_by_credential_id("nope") is None


async def test_list_by_user_returns_only_that_users_passkeys(
    passkey_repository: PasskeyRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    owner = await _create_user(user_repository, uow, "owner", role=Role.OWNER)
    other = await _create_user(user_repository, uow, "other")

    await passkey_repository.create(_create_dto(owner.id, "cred-owner"))
    await passkey_repository.create(_create_dto(other.id, "cred-other"))

    owner_passkeys = await passkey_repository.list_by_user(owner.id)
    assert len(owner_passkeys) == 1
    assert owner_passkeys[0].credential_id == "cred-owner"


async def test_get_by_id_and_user_rejects_other_users_passkey(
    passkey_repository: PasskeyRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    owner = await _create_user(user_repository, uow, "owner", role=Role.OWNER)
    other = await _create_user(user_repository, uow, "other")
    created = await passkey_repository.create(_create_dto(owner.id))

    assert await passkey_repository.find_by_id_and_user(created.id, owner.id) is not None
    assert await passkey_repository.find_by_id_and_user(created.id, other.id) is None


async def test_update_name(
    passkey_repository: PasskeyRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner", role=Role.OWNER)
    created = await passkey_repository.create(_create_dto(user.id))

    updated = await passkey_repository.update_name(created.id, "Renamed")
    assert updated.name == "Renamed"


async def test_update_after_authentication_bumps_sign_count_and_last_used_at(
    passkey_repository: PasskeyRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner", role=Role.OWNER)
    created = await passkey_repository.create(_create_dto(user.id))
    assert created.last_used_at is None

    await passkey_repository.update_after_authentication(created.id, 5)

    updated = await passkey_repository.find_by_credential_id("cred-1")
    assert updated is not None
    assert updated.sign_count == 5
    assert updated.last_used_at is not None


async def test_delete_by_id_and_user(
    passkey_repository: PasskeyRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner", role=Role.OWNER)
    created = await passkey_repository.create(_create_dto(user.id))

    deleted = await passkey_repository.delete_by_id_and_user(created.id, user.id)
    assert deleted
    assert await passkey_repository.find_by_credential_id("cred-1") is None


async def test_delete_by_id_and_user_rejects_other_users_passkey(
    passkey_repository: PasskeyRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    owner = await _create_user(user_repository, uow, "owner", role=Role.OWNER)
    other = await _create_user(user_repository, uow, "other")
    created = await passkey_repository.create(_create_dto(owner.id))

    deleted = await passkey_repository.delete_by_id_and_user(created.id, other.id)
    assert not deleted
    assert await passkey_repository.find_by_credential_id("cred-1") is not None
