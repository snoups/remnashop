from dataclasses import replace

from loguru import logger

from app.core.actor import Actor, actor_user_id
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.dto import AdLinkDto, CreateAdLinkDto
from app.modules.advertising.events import AdLinkChangedEvent
from app.modules.advertising.repository import AdLinkRepository


class CreateAdLinkUseCase(UseCase[CreateAdLinkDto, AdLinkDto]):
    required_permission = Permission.AD_LINKS_CREATE

    def __init__(
        self, ad_link_repository: AdLinkRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._ad_link_repository = ad_link_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: CreateAdLinkDto) -> AdLinkDto:
        async with self._uow:
            ad_link = await self._ad_link_repository.create(
                replace(data, created_by=actor_user_id(actor))
            )
            await self._event_publisher.publish(
                AdLinkChangedEvent(actor=actor, action="create", ad_link_id=ad_link.id)
            )
        logger.info(f"{actor.log} Created ad link '{ad_link.code}'")
        return ad_link
