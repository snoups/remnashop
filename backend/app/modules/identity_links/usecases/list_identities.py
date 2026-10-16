from app.core.db.uow import UnitOfWork
from app.modules.identity_links.dto import IdentityDto
from app.modules.identity_links.identities import build_identities
from app.modules.oauth import OAuthIdentityRepository
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


class ListIdentitiesUseCase:
    def __init__(
        self,
        settings_repository: SettingsRepository,
        oauth_identity_repository: OAuthIdentityRepository,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._oauth_identity_repository = oauth_identity_repository
        self._uow = uow

    async def execute(self, user: UserDto) -> list[IdentityDto]:
        async with self._uow:
            cabinet = await self._settings_repository.get_cabinet_auth_settings()
            oauth_identities = await self._oauth_identity_repository.list_by_user(user.id)
        return build_identities(user, cabinet, oauth_identities)
