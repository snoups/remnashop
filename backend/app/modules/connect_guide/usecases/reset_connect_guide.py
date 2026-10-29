from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.connect_guide.dto import ConnectGuideDto, ResetConnectGuideDto
from app.modules.connect_guide.events import ConnectGuideChangedEvent
from app.modules.connect_guide.repository import ConnectGuideRepository


class ResetConnectGuideUseCase(UseCase[ResetConnectGuideDto, ConnectGuideDto]):
    required_permission = Permission.CONNECT_GUIDE_RESET

    def __init__(
        self,
        connect_guide_repository: ConnectGuideRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._connect_guide_repository = connect_guide_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: ResetConnectGuideDto) -> ConnectGuideDto:
        async with self._uow:
            settings = await self._connect_guide_repository.reset()
            await self._event_publisher.publish(
                ConnectGuideChangedEvent(actor=actor, action="reset", ip_address=data.client_ip)
            )
        logger.info(f"{actor.log} Reset connect guide")
        return settings
