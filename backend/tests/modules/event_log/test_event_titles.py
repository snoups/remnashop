import dataclasses
import importlib
import json
import pkgutil
import typing
from pathlib import Path
from typing import Any, Final

import pytest

import app as app_package
import app.modules
from app.core.events import BaseEvent

_LOCALES_DIR: Final[Path] = (
    Path(app_package.__file__).parents[2] / "frontend" / "src" / "shared" / "i18n" / "locales"
)


def _event_classes() -> dict[str, type[BaseEvent]]:
    for module in pkgutil.iter_modules(app.modules.__path__):
        try:
            importlib.import_module(f"app.modules.{module.name}.events")
        except ModuleNotFoundError:
            continue
    found: dict[str, type[BaseEvent]] = {}
    pending = list(BaseEvent.__subclasses__())
    while pending:
        cls = pending.pop()
        pending.extend(cls.__subclasses__())
        # events declared inside tests aren't shown in the dashboard
        if hasattr(cls, "category") and cls.__module__.startswith("app."):
            found[cls.__name__] = cls
    return found


def _action_values(cls: type[BaseEvent]) -> set[str]:
    if not any(field.name == "action" for field in dataclasses.fields(cls)):
        return set()
    hint: Any = typing.get_type_hints(cls)["action"]
    return set(typing.get_args(hint))


def _event_log_locale(locale: str) -> dict[str, Any]:
    data = json.loads((_LOCALES_DIR / f"{locale}.json").read_text(encoding="utf-8"))
    return typing.cast(dict[str, Any], data["eventLog"])


@pytest.mark.parametrize("locale", ["en", "ru"])
def test_every_event_has_a_title_in_the_dashboard(locale: str) -> None:
    assert _event_classes().keys() - _event_log_locale(locale)["events"].keys() == set()


@pytest.mark.parametrize("locale", ["en", "ru"])
def test_every_event_action_has_a_title(locale: str) -> None:
    # the dashboard titles an event by its `action`, so each value needs its own text
    variants = _event_log_locale(locale)["eventVariants"]
    missing = [
        f"{name}.{action}"
        for name, cls in _event_classes().items()
        for action in _action_values(cls)
        if action not in variants.get(name, {})
    ]
    assert missing == []
