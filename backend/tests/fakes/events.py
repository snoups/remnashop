from app.core.events import BaseEvent


class RecordingEventPublisher:
    def __init__(self) -> None:
        self.events: list[BaseEvent] = []

    async def publish(self, event: BaseEvent) -> None:
        self.events.append(event)
