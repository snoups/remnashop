import contextlib
import dataclasses
from typing import Any, Final, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor, SyntheticActor
from app.core.db.models import EventOutboxEntry
from app.core.events import ActorEvent, BaseEvent, UserEvent

_SKIPPED_PAYLOAD_FIELDS: Final[set[str]] = {"event_id", "occurred_at", "ip_address"}


def _sanitize_user(user: Actor) -> dict[str, Any]:
    return {
        "id": user.id,
        "login": user.login,
        "name": user.name,
        "role": str(user.role),
        "telegram_id": user.telegram_id,
        "username": getattr(user, "username", None),  # not on SyntheticActor
        "email": user.email,
    }


def _build_payload(event: BaseEvent) -> dict[str, Any]:
    # Deferred import: modules.users imports app.core.events at module scope,
    # so an eager import here would cycle -- same reasoning as UserEvent.user's
    # TYPE_CHECKING-only import in core/events.py, except this needs the real
    # class for isinstance(), not just a type hint.
    from app.modules.users import UserDto  # noqa: PLC0415

    payload: dict[str, Any] = {}
    for f in dataclasses.fields(event):
        if f.name in _SKIPPED_PAYLOAD_FIELDS:
            continue
        value = getattr(event, f.name)
        payload[f.name] = (
            _sanitize_user(value) if isinstance(value, (UserDto, SyntheticActor)) else value
        )
    return payload


def _actor_fields(
    event: BaseEvent,
) -> tuple[Optional[int], Optional[str], Optional[str], Optional[str]]:
    if isinstance(event, ActorEvent):
        actor = event.actor
    elif isinstance(event, UserEvent):
        actor = event.user
    else:
        return None, None, None, None
    actor_id = actor.id if actor.id > 0 else None
    return actor_id, actor.login, actor.name, actor.email


class OutboxEventPublisher:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def publish(self, event: BaseEvent) -> None:
        actor_id, actor_login, actor_name, actor_email = _actor_fields(event)
        entry = EventOutboxEntry(
            category=event.category,
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            actor_id=actor_id,
            actor_login=actor_login,
            actor_name=actor_name,
            actor_email=actor_email,
            ip_address=event.ip_address,
            payload=_build_payload(event),
        )
        self._session.add(entry)
        await self._session.flush()  # assigns entry.id, still inside the caller's transaction

        # Fires before this transaction commits, so the worker's read
        # (get_unprocessed_by_id) frequently sees no row yet and no-ops --
        # normal under any DB pool contention, not exceptional. Either way
        # sweep_outbox_task picks the row up on its next pass; nothing is
        # lost, and correctness never depends on this trigger winning.
        from app.modules.event_log.tasks import process_outbox_entry_task  # noqa: PLC0415

        with contextlib.suppress(Exception):
            await process_outbox_entry_task.kiq(outbox_id=entry.id)  # type: ignore[call-overload]
