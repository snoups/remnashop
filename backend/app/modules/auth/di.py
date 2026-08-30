from dishka import Provider, Scope, alias, provide
from redis.asyncio import Redis

from app.core.ports import SessionRevoker
from app.modules.auth.oauth.state_store import OAuthStateStore
from app.modules.auth.repository import OAuthIdentityRepository, SessionRepository
from app.modules.auth.session_issuer import SessionIssuer
from app.modules.auth.usecases import (
    BootstrapOwnerUseCase,
    GetAuthStatusUseCase,
    ListOAuthIdentitiesUseCase,
    ListSessionsUseCase,
    ListUserSessionsUseCase,
    LoginUseCase,
    LogoutUseCase,
    OAuthConnectAuthorizeUseCase,
    OAuthConnectCallbackUseCase,
    OAuthDisconnectUseCase,
    OAuthLoginAuthorizeUseCase,
    OAuthLoginCallbackUseCase,
    RefreshSessionUseCase,
    RevokeSessionUseCase,
    RevokeUserSessionUseCase,
)


class AuthProvider(Provider):
    scope = Scope.REQUEST

    bootstrap_owner_use_case = provide(BootstrapOwnerUseCase)
    login_use_case = provide(LoginUseCase)
    get_auth_status_use_case = provide(GetAuthStatusUseCase)
    oauth_identity_repository = provide(OAuthIdentityRepository)
    session_repository = provide(SessionRepository)
    session_revoker = alias(source=SessionRepository, provides=SessionRevoker)
    session_issuer = provide(SessionIssuer)
    refresh_session_use_case = provide(RefreshSessionUseCase)
    logout_use_case = provide(LogoutUseCase)
    list_sessions_use_case = provide(ListSessionsUseCase)
    revoke_session_use_case = provide(RevokeSessionUseCase)
    list_user_sessions_use_case = provide(ListUserSessionsUseCase)
    revoke_user_session_use_case = provide(RevokeUserSessionUseCase)
    oauth_login_authorize_use_case = provide(OAuthLoginAuthorizeUseCase)
    oauth_login_callback_use_case = provide(OAuthLoginCallbackUseCase)
    oauth_connect_authorize_use_case = provide(OAuthConnectAuthorizeUseCase)
    oauth_connect_callback_use_case = provide(OAuthConnectCallbackUseCase)
    oauth_disconnect_use_case = provide(OAuthDisconnectUseCase)
    list_oauth_identities_use_case = provide(ListOAuthIdentitiesUseCase)

    @provide
    def get_oauth_state_store(self, redis: Redis) -> OAuthStateStore:
        return OAuthStateStore(redis)


def get_auth_providers() -> list[Provider]:
    return [AuthProvider()]
