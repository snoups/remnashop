from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.event_log.dto import EventLogEntryDto
from app.modules.event_log.ip_masking import mask_staff_ips
from app.modules.event_log.repository import EventLogRepository


class GetEventLogEntryUseCase(UseCase[int, EventLogEntryDto]):
    required_permission = Permission.EVENT_LOG_DETAIL_VIEW

    def __init__(self, event_log_repository: EventLogRepository, uow: UnitOfWork) -> None:
        self._event_log_repository = event_log_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> EventLogEntryDto:
        async with self._uow:
            entry = await self._event_log_repository.get_by_id(data)
            (masked,) = await mask_staff_ips(self._event_log_repository, actor, [entry])
            return masked
