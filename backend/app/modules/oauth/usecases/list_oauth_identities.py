from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.oauth.dto import OAuthIdentityDto
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.users import UserDto


class ListOAuthIdentitiesUseCase(UseCase[None, list[OAuthIdentityDto]]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(
        self,
        oauth_identity_repository: OAuthIdentityRepository,
        uow: UnitOfWork,
    ) -> None:
        self._oauth_identity_repository = oauth_identity_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> list[OAuthIdentityDto]:
        async with self._uow:
            return await self._oauth_identity_repository.list_by_user(actor.id)
