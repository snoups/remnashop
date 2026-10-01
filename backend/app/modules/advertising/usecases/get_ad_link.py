from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.dto import AdLinkDto
from app.modules.advertising.repository import AdLinkRepository


class GetAdLinkUseCase(UseCase[int, AdLinkDto]):
    required_permission = Permission.AD_LINKS_DETAIL_VIEW

    def __init__(self, ad_link_repository: AdLinkRepository, uow: UnitOfWork) -> None:
        self._ad_link_repository = ad_link_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> AdLinkDto:
        async with self._uow:
            return await self._ad_link_repository.get_by_id(data)
