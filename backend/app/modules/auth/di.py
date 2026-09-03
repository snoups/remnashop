from dishka import Provider, Scope, alias, provide

from app.core.ports import SessionRevoker
from app.modules.auth.repository import SessionRepository
from app.modules.auth.session_issuer import SessionIssuer
from app.modules.auth.usecases import (
    BootstrapOwnerUseCase,
    GetAuthStatusUseCase,
    ListSessionsUseCase,
    ListUserSessionsUseCase,
    LoginUseCase,
    LogoutUseCase,
    RefreshSessionUseCase,
    RevokeSessionUseCase,
    RevokeUserSessionUseCase,
)


class AuthProvider(Provider):
    scope = Scope.REQUEST

    bootstrap_owner_use_case = provide(BootstrapOwnerUseCase)
    login_use_case = provide(LoginUseCase)
    get_auth_status_use_case = provide(GetAuthStatusUseCase)
    session_repository = provide(SessionRepository)
    session_revoker = alias(source=SessionRepository, provides=SessionRevoker)
    session_issuer = provide(SessionIssuer)
    refresh_session_use_case = provide(RefreshSessionUseCase)
    logout_use_case = provide(LogoutUseCase)
    list_sessions_use_case = provide(ListSessionsUseCase)
    revoke_session_use_case = provide(RevokeSessionUseCase)
    list_user_sessions_use_case = provide(ListUserSessionsUseCase)
    revoke_user_session_use_case = provide(RevokeUserSessionUseCase)


def get_auth_providers() -> list[Provider]:
    return [AuthProvider()]
