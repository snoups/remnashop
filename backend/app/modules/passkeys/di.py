from dishka import Provider, Scope, alias, provide, provide_all
from redis.asyncio import Redis

from app.core.ports import PasskeyRevoker
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
    use_cases = provide_all(
        ListPasskeysUseCase,
        GetPasskeyRegistrationOptionsUseCase,
        VerifyPasskeyRegistrationUseCase,
        RenamePasskeyUseCase,
        DeletePasskeyUseCase,
        GetPasskeyAuthenticationOptionsUseCase,
        VerifyPasskeyAuthenticationUseCase,
    )
    passkey_revoker = alias(source=PasskeyRepository, provides=PasskeyRevoker)

    @provide
    def get_passkey_challenge_store(self, redis: Redis) -> PasskeyChallengeStore:
        return PasskeyChallengeStore(redis)


def get_passkeys_providers() -> list[Provider]:
    return [PasskeysDIProvider()]
