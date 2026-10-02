from dishka import Provider, Scope, provide, provide_all

from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.api_tokens.usecases import (
    CreateApiTokenUseCase,
    ListApiTokensUseCase,
    RevokeApiTokenUseCase,
)


class ApiTokensProvider(Provider):
    scope = Scope.REQUEST

    api_token_repository = provide(ApiTokenRepository)
    use_cases = provide_all(
        CreateApiTokenUseCase,
        ListApiTokensUseCase,
        RevokeApiTokenUseCase,
    )


def get_api_tokens_providers() -> list[Provider]:
    return [ApiTokensProvider()]
