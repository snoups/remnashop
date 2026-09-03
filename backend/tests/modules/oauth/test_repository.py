from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, OAuthProvider, Role
from app.modules.oauth.dto import CreateOAuthIdentityDto
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository


async def _create_user(user_repository: UserRepository, uow: UnitOfWork, login: str) -> UserDto:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login=login, name=login, role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()
    return user


async def test_create_then_get_by_provider_external_id(
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await _create_user(user_repository, uow, "owner")

    created = await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id,
            provider=OAuthProvider.GITHUB,
            external_id="12345",
            external_login="octocat",
        )
    )
    assert created.external_id == "12345"

    found = await oauth_identity_repository.get_by_provider_external_id(
        OAuthProvider.GITHUB, "12345"
    )
    assert found is not None
    assert found.user_id == user.id
    assert found.external_login == "octocat"


async def test_get_by_provider_external_id_returns_none_when_missing(
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    found = await oauth_identity_repository.get_by_provider_external_id(
        OAuthProvider.GITHUB, "nope"
    )
    assert found is None


async def test_create_upserts_for_same_user_and_provider(
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await _create_user(user_repository, uow, "owner")

    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id, provider=OAuthProvider.GITHUB, external_id="111", external_login="old"
        )
    )
    updated = await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id, provider=OAuthProvider.GITHUB, external_id="222", external_login="new"
        )
    )

    assert updated.external_id == "222"
    identities = await oauth_identity_repository.list_by_user(user.id)
    assert len(identities) == 1
    assert identities[0].external_id == "222"


async def test_list_by_user_returns_all_providers(
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await _create_user(user_repository, uow, "owner")

    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id, provider=OAuthProvider.GITHUB, external_id="111", external_login=None
        )
    )
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id, provider=OAuthProvider.TELEGRAM, external_id="222", external_login=None
        )
    )

    identities = await oauth_identity_repository.list_by_user(user.id)
    assert {identity.provider for identity in identities} == {
        OAuthProvider.GITHUB,
        OAuthProvider.TELEGRAM,
    }


async def test_delete_by_user_and_provider(
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id, provider=OAuthProvider.GITHUB, external_id="111", external_login=None
        )
    )

    deleted = await oauth_identity_repository.delete_by_user_and_provider(
        user.id, OAuthProvider.GITHUB
    )
    assert deleted

    identities = await oauth_identity_repository.list_by_user(user.id)
    assert identities == []


async def test_delete_by_user_and_provider_returns_false_when_missing(
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    deleted = await oauth_identity_repository.delete_by_user_and_provider(
        user.id, OAuthProvider.GITHUB
    )
    assert not deleted
