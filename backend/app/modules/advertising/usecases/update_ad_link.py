from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.dto import AdLinkDto, UpdateAdLinkDto
from app.modules.advertising.events import AdLinkChangedEvent
from app.modules.advertising.repository import AdLinkRepository


class UpdateAdLinkUseCase(UseCase[UpdateAdLinkDto, AdLinkDto]):
    required_permission = Permission.AD_LINKS_UPDATE

    def __init__(
        self, ad_link_repository: AdLinkRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._ad_link_repository = ad_link_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdateAdLinkDto) -> AdLinkDto:
        async with self._uow:
            ad_link = await self._ad_link_repository.update(data)
            await self._event_publisher.publish(
                AdLinkChangedEvent(actor=actor, action="update", ad_link_id=ad_link.id)
            )
        logger.info(f"{actor.log} Updated ad link '{data.ad_link_id}'")
        return ad_link
