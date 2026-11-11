import dataclasses
import json
from typing import Final

from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.constants import REDIS_KEY_PREFIX
from app.core.db.uow import UnitOfWork
from app.core.events import EVENT_ROW_FIELDS, SystemEvent
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.notifications import DeliverNotificationDto, DeliverNotificationUseCase
from app.modules.overview.events import SystemHealthDegradedEvent, SystemHealthRestoredEvent
from app.modules.overview.system_health import (
    HealthState,
    advance,
    read_health_problems,
)

_STATE_KEY: Final[str] = f"{REDIS_KEY_PREFIX}system_health:state"


class CheckSystemHealthUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(
        self,
        redis: Redis,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        deliver_notification_use_case: DeliverNotificationUseCase,
    ) -> None:
        self._redis = redis
        self._uow = uow
        self._event_publisher = event_publisher
        self._deliver_notification_use_case = deliver_notification_use_case

    async def _execute(self, actor: Actor, data: None) -> None:
        raw = await self._redis.get(_STATE_KEY)
        state = HealthState(**json.loads(raw)) if raw else HealthState(streaks={}, alerted={})
        transition = advance(state, await read_health_problems(self._redis))
        events: list[SystemEvent] = [
            SystemHealthDegradedEvent(
                kind=p.kind.value, subject=p.subject or "", value=p.value or 0
            )
            for p in transition.degraded
        ]
        for key in transition.restored:
            kind, _, subject = key.partition(":")
            events.append(SystemHealthRestoredEvent(kind=kind, subject=subject))
        for event in events:
            await self._deliver(event)
        async with self._uow:
            for event in events:
                await self._event_publisher.publish(event)
        await self._redis.set(_STATE_KEY, json.dumps(dataclasses.asdict(transition.state)))

    async def _deliver(self, event: SystemEvent) -> None:
        # sent from here, not by the worker's outbox subscriber: a stopped worker
        # is one of the things being reported
        payload = {k: v for k, v in dataclasses.asdict(event).items() if k not in EVENT_ROW_FIELDS}
        await self._deliver_notification_use_case.system(
            DeliverNotificationDto(
                event_type=event.event_type, payload=payload, actor_id=None, ip_address=None
            )
        )
