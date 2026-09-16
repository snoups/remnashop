from typing import Any, Protocol, runtime_checkable

from app.core.events import BaseEvent


@runtime_checkable
class EventPublisher(Protocol):
    async def publish(self, event: BaseEvent) -> None: ...


@runtime_checkable
class SessionRevoker(Protocol):
    async def revoke_all_by_user(self, user_id: int) -> None: ...


@runtime_checkable
class SubscriptionRevoker(Protocol):
    async def revoke_all_by_user(self, user_id: int) -> None: ...


@runtime_checkable
class PasskeyRevoker(Protocol):
    async def delete_all_by_user(self, user_id: int) -> int: ...


@runtime_checkable
class TranslatorRunner(Protocol):
    def get(self, key: str, obj: Any = None, **kwargs: Any) -> str: ...

    def from_event(self, event: Any, **kwargs: Any) -> str: ...

    def __call__(self, obj: Any = None, **kwargs: Any) -> str: ...

    def __getattr__(self, item: str) -> "TranslatorRunner": ...


@runtime_checkable
class TranslatorHub(Protocol):
    def get_translator_by_locale(self, locale: str) -> TranslatorRunner: ...
