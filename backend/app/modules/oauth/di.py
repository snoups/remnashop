from dishka import Provider, Scope, provide, provide_all
from redis.asyncio import Redis

from app.modules.oauth.providers.state_store import OAuthStateStore
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.oauth.usecases import (
    CleanupOidcIdentitiesUseCase,
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
    use_cases = provide_all(
        OAuthLoginAuthorizeUseCase,
        OAuthLoginCallbackUseCase,
        OAuthConnectAuthorizeUseCase,
        OAuthConnectCallbackUseCase,
        OAuthDisconnectUseCase,
        ListOAuthIdentitiesUseCase,
        CleanupOidcIdentitiesUseCase,
    )

    @provide
    def get_oauth_state_store(self, redis: Redis) -> OAuthStateStore:
        return OAuthStateStore(redis)


def get_oauth_providers() -> list[Provider]:
    return [OAuthDIProvider()]
