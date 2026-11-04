from dishka import Provider, Scope, alias, provide_all

from app.modules.auth.repository import SessionRepository
from app.modules.auth.session_issuer import SessionIssuer
from app.modules.auth.sign_in_methods import SignInMethodGuard
from app.modules.auth.usecases import (
    BootstrapOwnerUseCase,
    GetAuthStatusUseCase,
    ListSessionsUseCase,
    ListUserSessionsUseCase,
    LoginUseCase,
    LogoutUseCase,
    PruneStaleSessionsUseCase,
    RefreshSessionUseCase,
    RevokeOtherCabinetSessionsUseCase,
    RevokeOtherSessionsUseCase,
    RevokeSessionUseCase,
    RevokeUserSessionUseCase,
)
from app.modules.settings import AudienceSessionRevoker
from app.modules.users import SessionRevoker


class AuthProvider(Provider):
    scope = Scope.REQUEST

    services = provide_all(
        SessionRepository,
        SessionIssuer,
        SignInMethodGuard,
    )
    use_cases = provide_all(
        BootstrapOwnerUseCase,
        LoginUseCase,
        GetAuthStatusUseCase,
        RefreshSessionUseCase,
        LogoutUseCase,
        ListSessionsUseCase,
        RevokeSessionUseCase,
        RevokeOtherSessionsUseCase,
        RevokeOtherCabinetSessionsUseCase,
        ListUserSessionsUseCase,
        RevokeUserSessionUseCase,
        PruneStaleSessionsUseCase,
    )
    session_revoker = alias(source=SessionRepository, provides=SessionRevoker)
    audience_session_revoker = alias(source=SessionRepository, provides=AudienceSessionRevoker)


def get_auth_providers() -> list[Provider]:
    return [AuthProvider()]
