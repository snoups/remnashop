from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.auth.dto import OAuthIdentityDto
from app.modules.auth.repository import OAuthIdentityRepository
from app.modules.users import UserDto


class ListOAuthIdentitiesUseCase(UseCase[None, list[OAuthIdentityDto]]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, oauth_identity_repository: OAuthIdentityRepository) -> None:
        self._oauth_identity_repository = oauth_identity_repository

    async def _execute(self, actor: UserDto, data: None) -> list[OAuthIdentityDto]:
        return await self._oauth_identity_repository.list_by_user(actor.id)
