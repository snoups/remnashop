import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable

from loguru import logger

from app.core.events import BaseEvent

EventHandler = Callable[[Any], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[BaseEvent], list[EventHandler]] = defaultdict(list)
        self._catch_all_handlers: list[EventHandler] = []
        self._pending_tasks: set[asyncio.Task[None]] = set()

    def subscribe(self, event_type: type[BaseEvent], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        self._catch_all_handlers.append(handler)

    async def publish(self, event: BaseEvent) -> None:
        handlers = [*self._handlers.get(type(event), []), *self._catch_all_handlers]
        task = asyncio.create_task(self._dispatch(event, handlers))
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _dispatch(self, event: BaseEvent, handlers: list[EventHandler]) -> None:
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                # One subscriber failing (e.g. a future notification handler hitting
                # a network error, or an event published without a `category`) must
                # not break the publisher's own flow or the other subscribers -- a
                # failed login shouldn't fail to log because a Telegram notification
                # handler threw.
                logger.exception(f"Event handler '{handler}' failed for '{event.event_type}'")

    def autodiscover(self) -> None:
        # Imported here, not at module level: modules/*/events.py sits downstream
        # of core, so importing it eagerly at import time would be circular.
        from app.modules.auth.events import (  # noqa: PLC0415
            register_subscribers as register_auth_subscribers,
        )
        from app.modules.event_log.subscribers import (  # noqa: PLC0415
            register_subscribers as register_event_log_subscribers,
        )
        from app.modules.translations.events import (  # noqa: PLC0415
            register_subscribers as register_translations_subscribers,
        )

        register_auth_subscribers(self)
        register_event_log_subscribers(self)
        register_translations_subscribers(self)

        handler_count = sum(len(handlers) for handlers in self._handlers.values())
        handler_count += len(self._catch_all_handlers)
        logger.debug(f"Event bus autodiscovery complete: {handler_count} handler(s) registered")

    async def shutdown(self) -> None:
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
        self._handlers.clear()
        self._catch_all_handlers.clear()
