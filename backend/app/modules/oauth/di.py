from dishka import Provider, Scope, alias, provide, provide_all
from redis.asyncio import Redis

from app.core.ports import OidcIdentityCleaner
from app.modules.oauth.providers.state_store import OAuthStateStore
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.oauth.usecases import (
    ListOAuthIdentitiesUseCase,
    OAuthConnectAuthorizeUseCase,
    OAuthConnectCallbackUseCase,
    OAuthDisconnectUseCase,
    OAuthLoginAuthorizeUseCase,
    OAuthLoginCallbackUseCase,
)


class OAuthDIProvider(Provider):
    scope = Scope.REQUEST

    oauth_identity_repository = provide(OAuthIdentityRepository)
    oidc_identity_cleaner = alias(source=OAuthIdentityRepository, provides=OidcIdentityCleaner)
    use_cases = provide_all(
        OAuthLoginAuthorizeUseCase,
        OAuthLoginCallbackUseCase,
        OAuthConnectAuthorizeUseCase,
        OAuthConnectCallbackUseCase,
        OAuthDisconnectUseCase,
        ListOAuthIdentitiesUseCase,
    )

    @provide
    def get_oauth_state_store(self, redis: Redis) -> OAuthStateStore:
        return OAuthStateStore(redis)


def get_oauth_providers() -> list[Provider]:
    return [OAuthDIProvider()]
