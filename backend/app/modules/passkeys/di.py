from dishka import Provider, Scope, provide
from redis.asyncio import Redis

from app.modules.passkeys.challenge_store import PasskeyChallengeStore
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.passkeys.usecases import (
    DeletePasskeyUseCase,
    GetPasskeyAuthenticationOptionsUseCase,
    GetPasskeyRegistrationOptionsUseCase,
    ListPasskeysUseCase,
    RenamePasskeyUseCase,
    VerifyPasskeyAuthenticationUseCase,
    VerifyPasskeyRegistrationUseCase,
)


class PasskeysDIProvider(Provider):
    scope = Scope.REQUEST

    passkey_repository = provide(PasskeyRepository)
    list_passkeys_use_case = provide(ListPasskeysUseCase)
    get_registration_options_use_case = provide(GetPasskeyRegistrationOptionsUseCase)
    verify_registration_use_case = provide(VerifyPasskeyRegistrationUseCase)
    rename_passkey_use_case = provide(RenamePasskeyUseCase)
    delete_passkey_use_case = provide(DeletePasskeyUseCase)
    get_authentication_options_use_case = provide(GetPasskeyAuthenticationOptionsUseCase)
    verify_authentication_use_case = provide(VerifyPasskeyAuthenticationUseCase)

    @provide
    def get_passkey_challenge_store(self, redis: Redis) -> PasskeyChallengeStore:
        return PasskeyChallengeStore(redis)


def get_passkey_providers() -> list[Provider]:
    return [PasskeysDIProvider()]
