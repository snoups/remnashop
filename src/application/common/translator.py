from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TranslatorRunner(Protocol):
    def get(self, key: str, obj: Any = None, **kwargs: Any) -> str: ...

    def __call__(self, obj: Any = None, **kwargs: Any) -> str: ...

    def __getattr__(self, item: str) -> "TranslatorRunner": ...


@runtime_checkable
class TranslatorHub(Protocol):
    def get_translator_by_locale(self, locale: str) -> TranslatorRunner: ...
