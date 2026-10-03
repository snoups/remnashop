from typing import Any, Optional

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.event_bus import EventBus
from app.core.events import StoredEvent
from app.core.usecase import UseCase
from app.modules.event_log.dto import EventLogEntryDto
from app.modules.event_log.outbox_repository import EventOutboxRepository
from app.modules.event_log.repository import EventLogRepository


def _target_id(payload: dict[str, Any]) -> Optional[int]:
    # ActorTargetEvent's target, as the outbox publisher serialized it
    target = payload.get("target")
    target_id = target.get("id") if isinstance(target, dict) else None
    return target_id if isinstance(target_id, int) and target_id > 0 else None


class ProcessOutboxEntryUseCase(UseCase[int, None]):
    required_permission = None

    def __init__(
        self,
        outbox_repository: EventOutboxRepository,
        event_log_repository: EventLogRepository,
        bus: EventBus,
        uow: UnitOfWork,
    ) -> None:
        self._outbox_repository = outbox_repository
        self._event_log_repository = event_log_repository
        self._bus = bus
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> None:
        try:
            async with self._uow:
                row = await self._outbox_repository.get_unprocessed_by_id(data)
                if row is None:
                    return  # already processed, gone, or locked by another processor
                await self._event_log_repository.create(
                    EventLogEntryDto(
                        category=row.category,
                        event_type=row.event_type,
                        occurred_at=row.occurred_at,
                        actor_id=row.actor_id,
                        actor_login=row.actor_login,
                        actor_name=row.actor_name,
                        actor_email=row.actor_email,
                        ip_address=row.ip_address,
                        payload=row.payload,
                        outbox_id=row.id,
                        target_id=_target_id(row.payload),
                    )
                )
                error_message = await self._bus.dispatch_stored(
                    StoredEvent(
                        outbox_id=row.id,
                        category=row.category,
                        event_type=row.event_type,
                        occurred_at=row.occurred_at,
                        payload=row.payload,
                        actor_id=row.actor_id,
                        actor_login=row.actor_login,
                        actor_name=row.actor_name,
                        actor_email=row.actor_email,
                        ip_address=row.ip_address,
                    )
                )
                if error_message is not None:
                    # Handler failed. The audit row above still commits (idempotent
                    # on retry via outbox_id). Leave the row unprocessed so the next
                    # sweep re-dispatches; the attempts cap eventually stops it.
                    await self._outbox_repository.record_failure(row.id, error=error_message)
                else:
                    await self._outbox_repository.mark_processed(row.id)
        except Exception as error:
            # dispatch_stored never raises, so this is a DB error that broke the
            # transaction; the failure is recorded in a fresh one so attempts
            # still counts toward the cap
            async with self._uow:
                await self._outbox_repository.record_failure(data, error=str(error))
