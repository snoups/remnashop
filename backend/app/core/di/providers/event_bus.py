from dishka import Provider, Scope, alias, provide

from app.core.event_bus import EventBus
from app.core.ports import EventPublisher, EventSubscriber


class EventBusProvider(Provider):
    scope = Scope.APP

    event_bus = provide(EventBus, provides=EventBus)
    event_publisher = alias(source=EventBus, provides=EventPublisher)
    event_subscriber = alias(source=EventBus, provides=EventSubscriber)
