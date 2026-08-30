from dishka import Provider, Scope, provide

from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.api_tokens.usecases import (
    CreateApiTokenUseCase,
    ListApiTokensUseCase,
    RevokeApiTokenUseCase,
)


class ApiTokenProvider(Provider):
    scope = Scope.REQUEST

    api_token_repository = provide(ApiTokenRepository)
    create_api_token_use_case = provide(CreateApiTokenUseCase)
    list_api_tokens_use_case = provide(ListApiTokensUseCase)
    revoke_api_token_use_case = provide(RevokeApiTokenUseCase)


def get_api_tokens_providers() -> list[Provider]:
    return [ApiTokenProvider()]
