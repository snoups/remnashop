from typing import Optional

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.dto import UserAdAttributionDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.users import UserRepository, get_visible_target


class GetUserAdAttributionUseCase(UseCase[int, Optional[UserAdAttributionDto]]):
    required_permission = Permission.AD_LINKS_USER_ATTRIBUTION_VIEW

    def __init__(
        self, ad_link_repository: AdLinkRepository, user_repository: UserRepository, uow: UnitOfWork
    ) -> None:
        self._ad_link_repository = ad_link_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> Optional[UserAdAttributionDto]:
        async with self._uow:
            await get_visible_target(self._user_repository, actor, data)
            return await self._ad_link_repository.get_user_attribution(data)
