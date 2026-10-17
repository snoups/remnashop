from typing import Any, Protocol

from app.core.enums import Locale
from app.core.events import BaseEvent


class EventPublisher(Protocol):
    async def publish(self, event: BaseEvent) -> None: ...


class OutboxEntryDispatch(Protocol):
    async def kiq(self, *, outbox_id: int) -> object: ...


class BotSignals(Protocol):
    # tells a running telegram process to pick up a change made elsewhere
    async def restart(self) -> None: ...

    async def dialogs_changed(self) -> None: ...

    async def translation_changed(
        self, locale: Locale, message_id: str, attribute_id: str, value: str
    ) -> None: ...


class TranslatorRunner(Protocol):
    def get(self, key: str, obj: Any = None, **kwargs: Any) -> str: ...

    def from_event(self, event: Any, **kwargs: Any) -> str: ...

    def __call__(self, obj: Any = None, **kwargs: Any) -> str: ...

    def __getattr__(self, item: str) -> "TranslatorRunner": ...


class TranslatorHub(Protocol):
    def get_translator_by_locale(self, locale: str) -> TranslatorRunner: ...
