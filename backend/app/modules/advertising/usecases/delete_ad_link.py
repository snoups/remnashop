from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.events import AdLinkChangedEvent
from app.modules.advertising.repository import AdLinkRepository


class DeleteAdLinkUseCase(UseCase[int, None]):
    required_permission = Permission.AD_LINKS_DELETE

    def __init__(
        self, ad_link_repository: AdLinkRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._ad_link_repository = ad_link_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: int) -> None:
        async with self._uow:
            await self._ad_link_repository.delete_if_no_attributions(data)
            await self._event_publisher.publish(
                AdLinkChangedEvent(actor=actor, action="delete", ad_link_id=data)
            )
        logger.info(f"{actor.log} Deleted ad link '{data}'")
