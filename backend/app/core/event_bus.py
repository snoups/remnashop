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
        # Every handler still runs even if an earlier one fails (isolation
        # between handlers); the last failure's message is returned so the
        # outbox sweep can record it and retry the whole row -- retry is
        # row-level, not per-handler.
        error_message: Optional[str] = None
        for handler in self._handlers.get(entry.event_type, []):
            try:
                await handler(entry)
            except Exception as error:
                error_message = str(error)
                logger.exception(f"Event handler '{handler}' failed for '{entry.event_type}'")
        return error_message

    def autodiscover(self) -> None:
        # Imported here, not at module level: modules/*/events.py sits downstream
        # of core, so importing it eagerly at import time would be circular.
        from app.modules.auth.events import (  # noqa: PLC0415
            register_subscribers as register_auth_subscribers,
        )
        from app.modules.referrals.events import (  # noqa: PLC0415
            register_subscribers as register_referral_subscribers,
        )
        from app.modules.translations.events import (  # noqa: PLC0415
            register_subscribers as register_translations_subscribers,
        )

        register_auth_subscribers(self)
        register_referral_subscribers(self)
        register_translations_subscribers(self)

        handler_count = sum(len(handlers) for handlers in self._handlers.values())
        logger.debug(f"Event bus autodiscovery complete: {handler_count} handler(s) registered")

    async def shutdown(self) -> None:
        self._handlers.clear()
