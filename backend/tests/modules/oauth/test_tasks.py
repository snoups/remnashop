from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.modules.oauth.dto import CreateOAuthIdentityDto
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.oauth.usecases import CleanupOidcIdentitiesUseCase
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


async def test_cleanup_oidc_identities_deletes_only_oidc_rows(
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    oidc_user_a = await user_repository.create(CreateUserDto(name="oidc-a", telegram_id=501))
    oidc_user_b = await user_repository.create(CreateUserDto(name="oidc-b", telegram_id=502))
    github_user = await user_repository.create(CreateUserDto(name="gh", telegram_id=503))

    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=oidc_user_a.id,
            provider=OAuthProvider.OIDC,
            external_id="sub-a",
            external_login=None,
        )
    )
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=oidc_user_b.id,
            provider=OAuthProvider.OIDC,
            external_id="sub-b",
            external_login=None,
        )
    )
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=github_user.id,
            provider=OAuthProvider.GITHUB,
            external_id="gh-1",
            external_login="ghuser",
        )
    )

    await CleanupOidcIdentitiesUseCase(oauth_identity_repository, uow).system()

    assert await oauth_identity_repository.list_by_user(oidc_user_a.id) == []
    assert await oauth_identity_repository.list_by_user(oidc_user_b.id) == []
    remaining_github = await oauth_identity_repository.list_by_user(github_user.id)
    assert [identity.provider for identity in remaining_github] == [OAuthProvider.GITHUB]


async def test_cleanup_oidc_identities_is_a_noop_when_nothing_to_clean(
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    github_user = await user_repository.create(CreateUserDto(name="gh-only", telegram_id=504))
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=github_user.id,
            provider=OAuthProvider.GITHUB,
            external_id="gh-2",
            external_login="ghuser2",
        )
    )

    await CleanupOidcIdentitiesUseCase(oauth_identity_repository, uow).system()

    remaining_github = await oauth_identity_repository.list_by_user(github_user.id)
    assert [identity.provider for identity in remaining_github] == [OAuthProvider.GITHUB]
