import contextlib
import dataclasses
from functools import partial
from typing import Any, Optional

from app.core.actor import Actor, actor_user_id
from app.core.db.models import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.events import EVENT_ROW_FIELDS, ActorEvent, ActorSnapshot, BaseEvent, UserEvent
from app.core.ports import OutboxEntryDispatch


def _sanitize_user(user: Actor) -> dict[str, Any]:
    return ActorSnapshot.of(user).to_payload()


def _build_payload(event: BaseEvent) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for f in dataclasses.fields(event):
        if f.name in EVENT_ROW_FIELDS:
            continue
        value = getattr(event, f.name)
        payload[f.name] = _sanitize_user(value) if isinstance(value, Actor) else value
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
    actor_id = actor_user_id(actor)
    return actor_id, actor.login, actor.name, actor.email


class OutboxEventPublisher:
    def __init__(self, uow: UnitOfWork, dispatch: OutboxEntryDispatch) -> None:
        self._uow = uow
        self._dispatch = dispatch

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
        self._uow.session.add(entry)
        await self._uow.session.flush()  # assigns entry.id inside the caller's transaction
        await self._uow.after_commit(partial(self._kick, entry.id))

    async def _kick(self, outbox_id: int) -> None:
        # Fast path only: sweep_outbox_task picks up any row this misses, so a
        # broker hiccup must not fail a request whose transaction already committed.
        with contextlib.suppress(Exception):
            await self._dispatch.kiq(outbox_id=outbox_id)
