import importlib
import inspect
import pkgutil
from typing import Final

from dishka import FromComponent

import app.telegram.routers as routers

# keys aiogram puts into the data every getter receives as **kwargs
_AIOGRAM_DATA_KEYS: Final[frozenset[str]] = frozenset(
    {"bot", "state", "raw_state", "event_from_user", "event_chat", "dispatcher", "event_update"}
)
_INJECTED_MARKER: Final[type] = type(FromComponent())


def _getters() -> list[object]:
    found: list[object] = []
    for info in pkgutil.walk_packages(routers.__path__, f"{routers.__name__}."):
        if not info.name.endswith(".getters"):
            continue
        module = importlib.import_module(info.name)
        found += [
            obj
            for _, obj in inspect.getmembers(module, inspect.isfunction)
            if hasattr(obj, "__dishka_orig_func__")
        ]
    return found


def test_no_injected_getter_parameter_collides_with_aiogram_data() -> None:
    clashes = []
    for getter in _getters():
        original = getter.__dishka_orig_func__  # type: ignore[attr-defined]
        for name, parameter in inspect.signature(original).parameters.items():
            metadata = getattr(parameter.annotation, "__metadata__", ())
            injected = any(isinstance(item, _INJECTED_MARKER) for item in metadata)
            if injected and name in _AIOGRAM_DATA_KEYS:
                clashes.append(f"{original.__module__}.{original.__name__}({name})")
    assert not clashes, clashes
