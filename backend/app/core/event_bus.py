from functools import wraps
from typing import Awaitable, Callable, Optional

from loguru import logger

from app.core.events import E, StoredEvent, restore_event

StoredEventHandler = Callable[[StoredEvent], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[StoredEventHandler]] = {}

    def subscribe(
        self, event_type: type[E], handler: Callable[[E, StoredEvent], Awaitable[None]]
    ) -> None:
        @wraps(handler)
        async def run(entry: StoredEvent) -> None:
            # a row that no longer matches the class fails like any handler error
            await handler(restore_event(event_type, entry), entry)

        self._handlers.setdefault(event_type.__name__, []).append(run)

    def subscribe_stored(self, event_type: str, handler: StoredEventHandler) -> None:
        # for subscribers that only know event types as stored strings
        self._handlers.setdefault(event_type, []).append(handler)

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
