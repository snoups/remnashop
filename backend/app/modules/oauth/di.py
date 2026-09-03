from dishka import Provider, Scope, provide
from redis.asyncio import Redis

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
    oauth_login_authorize_use_case = provide(OAuthLoginAuthorizeUseCase)
    oauth_login_callback_use_case = provide(OAuthLoginCallbackUseCase)
    oauth_connect_authorize_use_case = provide(OAuthConnectAuthorizeUseCase)
    oauth_connect_callback_use_case = provide(OAuthConnectCallbackUseCase)
    oauth_disconnect_use_case = provide(OAuthDisconnectUseCase)
    list_oauth_identities_use_case = provide(ListOAuthIdentitiesUseCase)

    @provide
    def get_oauth_state_store(self, redis: Redis) -> OAuthStateStore:
        return OAuthStateStore(redis)


def get_oauth_providers() -> list[Provider]:
    return [OAuthDIProvider()]
