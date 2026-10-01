from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.repository import AdLinkRepository


class DeleteAdLinkUseCase(UseCase[int, None]):
    required_permission = Permission.AD_LINKS_DELETE

    def __init__(self, ad_link_repository: AdLinkRepository, uow: UnitOfWork) -> None:
        self._ad_link_repository = ad_link_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> None:
        async with self._uow:
            await self._ad_link_repository.delete_if_no_attributions(data)
        logger.info(f"{actor.log} Deleted ad link '{data}'")
