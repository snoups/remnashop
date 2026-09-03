from dishka import Provider, Scope, provide

from app.core.event_bus import EventBus
from app.core.outbox_event_publisher import OutboxEventPublisher
from app.core.ports import EventPublisher


class EventBusProvider(Provider):
    scope = Scope.APP

    event_bus = provide(EventBus, provides=EventBus)


class EventPublisherProvider(Provider):
    scope = Scope.REQUEST

    event_publisher = provide(OutboxEventPublisher, provides=EventPublisher)
