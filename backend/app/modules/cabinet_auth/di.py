from dishka import Provider, Scope, provide, provide_all

from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.devices import KnownDevices
from app.modules.cabinet_auth.email_codes import EmailCodeStore
from app.modules.cabinet_auth.sign_in import CabinetSignIn
from app.modules.cabinet_auth.usecases import (
    BotSignInUseCase,
    CabinetOAuthAuthorizeUseCase,
    CabinetOAuthCallbackUseCase,
    GetCabinetMethodsUseCase,
    GetCabinetProfileUseCase,
    IssueBotSignInLinkUseCase,
    RequestDeeplinkUseCase,
    RequestEmailCodeUseCase,
    TelegramWebAppLoginUseCase,
    VerifyEmailCodeUseCase,
)


class CabinetAuthProvider(Provider):
    scope = Scope.REQUEST

    use_cases = provide_all(
        BotSignInUseCase,
        IssueBotSignInLinkUseCase,
        CabinetOAuthAuthorizeUseCase,
        CabinetOAuthCallbackUseCase,
        RequestDeeplinkUseCase,
        GetCabinetMethodsUseCase,
        GetCabinetProfileUseCase,
        RequestEmailCodeUseCase,
        TelegramWebAppLoginUseCase,
        VerifyEmailCodeUseCase,
    )
    cabinet_sign_in = provide(CabinetSignIn)
    deeplink_store = provide(DeeplinkStore)
    known_devices = provide(KnownDevices)
    email_code_store = provide(EmailCodeStore)


def get_cabinet_auth_providers() -> list[Provider]:
    return [CabinetAuthProvider()]
