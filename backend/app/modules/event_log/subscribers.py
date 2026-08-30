from app.core.event_bus import EventBus
from app.core.events import ActorTargetEvent, BaseEvent, UserEvent
from app.modules.event_log.serializers import build_payload
from app.modules.event_log.tasks import persist_event_task


async def _persist_event(event: BaseEvent) -> None:
    payload = build_payload(event)

    actor_id = actor_login = actor_name = actor_email = None
    if isinstance(event, ActorTargetEvent):
        actor_id, actor_login, actor_name, actor_email = (
            event.actor.id,
            event.actor.login,
            event.actor.name,
            event.actor.email,
        )
    elif isinstance(event, UserEvent):
        actor_id, actor_login, actor_name, actor_email = (
            event.user.id,
            event.user.login,
            event.user.name,
            event.user.email,
        )

    # A synthetic actor (SYSTEM's id=-1, or an API token's id=0 -- see
    # modules/api_tokens) isn't a real row in `users`, but
    # event_log_entries.actor_id has a real FK there. Drop it to NULL rather
    # than violate that constraint; login/name/email still identify the
    # actor in the audit trail.
    if actor_id is not None and actor_id <= 0:
        actor_id = None

    # A known dishka+taskiq limitation: mypy can't see that repository/uow
    # are FromDishka-injected and don't belong in .kiq()'s own call signature.
    await persist_event_task.kiq(  # type: ignore[call-overload, misc]
        category=event.category.value,
        event_type=event.event_type,
        occurred_at=event.occurred_at.isoformat(),
        payload=payload,
        actor_id=actor_id,
        actor_login=actor_login,
        actor_name=actor_name,
        actor_email=actor_email,
        ip_address=event.ip_address,
    )


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe_all(_persist_event)
