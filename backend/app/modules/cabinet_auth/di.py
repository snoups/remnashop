from dishka import Provider, Scope, provide, provide_all
from redis.asyncio import Redis

from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.devices import KnownDevices
from app.modules.cabinet_auth.email_codes import EmailCodeStore
from app.modules.cabinet_auth.sign_in import CabinetSignIn
from app.modules.cabinet_auth.usecases import (
    CabinetOAuthAuthorizeUseCase,
    CabinetOAuthCallbackUseCase,
    ConfirmDeeplinkUseCase,
    GetCabinetMethodsUseCase,
    GetCabinetProfileUseCase,
    PollDeeplinkUseCase,
    RequestDeeplinkUseCase,
    RequestEmailCodeUseCase,
    TelegramWebAppLoginUseCase,
    VerifyEmailCodeUseCase,
)


class CabinetAuthProvider(Provider):
    scope = Scope.REQUEST

    use_cases = provide_all(
        CabinetOAuthAuthorizeUseCase,
        CabinetOAuthCallbackUseCase,
        ConfirmDeeplinkUseCase,
        PollDeeplinkUseCase,
        RequestDeeplinkUseCase,
        GetCabinetMethodsUseCase,
        GetCabinetProfileUseCase,
        RequestEmailCodeUseCase,
        TelegramWebAppLoginUseCase,
        VerifyEmailCodeUseCase,
    )
    sign_in = provide(CabinetSignIn)

    @provide
    def get_deeplink_store(self, redis: Redis) -> DeeplinkStore:
        return DeeplinkStore(redis)

    @provide
    def get_known_devices(self, redis: Redis) -> KnownDevices:
        return KnownDevices(redis)

    @provide
    def get_email_code_store(self, redis: Redis) -> EmailCodeStore:
        return EmailCodeStore(redis)


def get_cabinet_auth_providers() -> list[Provider]:
    return [CabinetAuthProvider()]
