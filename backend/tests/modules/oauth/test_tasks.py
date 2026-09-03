from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.modules.oauth.dto import CreateOAuthIdentityDto
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.oauth.tasks import cleanup_oidc_identities
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

    await cleanup_oidc_identities(oauth_identity_repository=oauth_identity_repository, uow=uow)

    assert (
        await oauth_identity_repository.get_by_user_and_provider(oidc_user_a.id, OAuthProvider.OIDC)
        is None
    )
    assert (
        await oauth_identity_repository.get_by_user_and_provider(oidc_user_b.id, OAuthProvider.OIDC)
        is None
    )
    remaining_github = await oauth_identity_repository.get_by_user_and_provider(
        github_user.id, OAuthProvider.GITHUB
    )
    assert remaining_github is not None


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

    await cleanup_oidc_identities(oauth_identity_repository=oauth_identity_repository, uow=uow)

    remaining_github = await oauth_identity_repository.get_by_user_and_provider(
        github_user.id, OAuthProvider.GITHUB
    )
    assert remaining_github is not None
