from app.core.db.uow import UnitOfWork
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.users import UserDto


class RevokeApiTokenUseCase(UseCase[int, None]):
    required_permission = Permission.API_TOKENS_MANAGE

    def __init__(self, api_token_repository: ApiTokenRepository, uow: UnitOfWork) -> None:
        self._api_token_repository = api_token_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> None:
        tokens = await self._api_token_repository.list_active()
        if not any(token.id == data for token in tokens):
            raise NotFoundError("API token not found")

        async with self._uow:
            await self._api_token_repository.revoke_by_id(data)
