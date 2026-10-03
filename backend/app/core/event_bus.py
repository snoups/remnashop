from typing import Any, Awaitable, Callable, Optional

from loguru import logger

from app.core.events import BaseEvent, StoredEvent

EventHandler = Callable[[Any], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event_type: type[BaseEvent], handler: EventHandler) -> None:
        self._handlers.setdefault(event_type.__name__, []).append(handler)

    async def dispatch_stored(self, entry: StoredEvent) -> Optional[str]:
        # every handler runs even if an earlier one failed; the last failure is
        # returned so the outbox sweep records it and retries the whole row
        error_message: Optional[str] = None
        for handler in self._handlers.get(entry.event_type, []):
            try:
                await handler(entry)
            except Exception as error:
                error_message = str(error)
                logger.exception(f"Event handler '{handler}' failed for '{entry.event_type}'")
        return error_message

    @property
    def handler_count(self) -> int:
        return sum(len(handlers) for handlers in self._handlers.values())

    async def shutdown(self) -> None:
        self._handlers.clear()
