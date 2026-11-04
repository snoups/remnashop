from app.core.actor import Actor
from app.core.events import visible_event_ip
from app.modules.event_log.dto import EventLogEntryDto
from app.modules.event_log.repository import EventLogRepository


async def mask_staff_ips(
    repository: EventLogRepository, reader: Actor, entries: list[EventLogEntryDto]
) -> list[EventLogEntryDto]:
    roles = await repository.roles_of({e.actor_id for e in entries if e.actor_id is not None})
    return [
        entry.model_copy(
            update={
                "ip_address": visible_event_ip(
                    reader,
                    entry.event_type,
                    entry.payload,
                    entry.ip_address,
                    roles.get(entry.actor_id) if entry.actor_id is not None else None,
                )
            }
        )
        for entry in entries
    ]
