from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.dto import AdLinkDto, UpdateAdLinkDto
from app.modules.advertising.repository import AdLinkRepository


class UpdateAdLinkUseCase(UseCase[UpdateAdLinkDto, AdLinkDto]):
    required_permission = Permission.AD_LINKS_UPDATE

    def __init__(self, ad_link_repository: AdLinkRepository, uow: UnitOfWork) -> None:
        self._ad_link_repository = ad_link_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: UpdateAdLinkDto) -> AdLinkDto:
        async with self._uow:
            ad_link = await self._ad_link_repository.update(data)
        logger.info(f"{actor.log} Updated ad link id={data.ad_link_id}")
        return ad_link
