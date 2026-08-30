from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.api_tokens.dto import ApiTokenDto
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.users import UserDto


class ListApiTokensUseCase(UseCase[None, list[ApiTokenDto]]):
    required_permission = Permission.API_TOKENS_MANAGE

    def __init__(self, api_token_repository: ApiTokenRepository) -> None:
        self._api_token_repository = api_token_repository

    async def _execute(self, actor: UserDto, data: None) -> list[ApiTokenDto]:
        return await self._api_token_repository.list_active()
