from dishka import Provider, Scope, alias, provide, provide_all

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
from app.modules.settings import OidcIdentityCleaner


class OAuthDIProvider(Provider):
    scope = Scope.REQUEST

    oauth_identity_repository = provide(OAuthIdentityRepository)
    oauth_state_store = provide(OAuthStateStore)
    oidc_identity_cleaner = alias(source=OAuthIdentityRepository, provides=OidcIdentityCleaner)
    use_cases = provide_all(
        OAuthLoginAuthorizeUseCase,
        OAuthLoginCallbackUseCase,
        OAuthConnectAuthorizeUseCase,
        OAuthConnectCallbackUseCase,
        OAuthDisconnectUseCase,
        ListOAuthIdentitiesUseCase,
    )


def get_oauth_providers() -> list[Provider]:
    return [OAuthDIProvider()]
