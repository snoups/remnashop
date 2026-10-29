from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.connect_guide.dto import ConnectGuideDto, UpdateConnectGuideDto
from app.modules.connect_guide.events import ConnectGuideChangedEvent
from app.modules.connect_guide.repository import ConnectGuideRepository


class UpdateConnectGuideUseCase(UseCase[UpdateConnectGuideDto, ConnectGuideDto]):
    required_permission = Permission.CONNECT_GUIDE_MANAGE

    def __init__(
        self,
        connect_guide_repository: ConnectGuideRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._connect_guide_repository = connect_guide_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: UpdateConnectGuideDto) -> ConnectGuideDto:
        async with self._uow:
            saved = await self._connect_guide_repository.save(data.enabled, data.catalog)
            await self._event_publisher.publish(
                ConnectGuideChangedEvent(actor=actor, action="update", ip_address=data.client_ip)
            )
        logger.info(f"{actor.log} Updated connect guide")
        return saved
