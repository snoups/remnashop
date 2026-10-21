import importlib
import pkgutil

import app.modules
from app.core.events import BaseEvent
from app.modules.notifications.dto import COALESCED_EVENT_TYPES, NOTIFICATION_GROUPS


def _event_class_names() -> set[str]:
    for module in pkgutil.iter_modules(app.modules.__path__):
        try:
            importlib.import_module(f"app.modules.{module.name}.events")
        except ModuleNotFoundError:
            continue
    names: set[str] = set()
    pending: list[type[BaseEvent]] = [BaseEvent]
    while pending:
        for subclass in pending.pop().__subclasses__():
            names.add(subclass.__name__)
            pending.append(subclass)
    return names


def test_every_grouped_and_coalesced_name_is_an_event_class() -> None:
    known = _event_class_names()
    named = frozenset().union(*NOTIFICATION_GROUPS.values()) | COALESCED_EVENT_TYPES

    assert named - known == set()
