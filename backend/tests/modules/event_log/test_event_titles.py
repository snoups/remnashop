import importlib
import json
import pkgutil
from pathlib import Path
from typing import Final

import pytest

import app as app_package
import app.modules
from app.core.events import BaseEvent

_LOCALES_DIR: Final[Path] = (
    Path(app_package.__file__).parents[2] / "frontend" / "src" / "shared" / "i18n" / "locales"
)


def _event_names() -> set[str]:
    for module in pkgutil.iter_modules(app.modules.__path__):
        try:
            importlib.import_module(f"app.modules.{module.name}.events")
        except ModuleNotFoundError:
            continue
    names: set[str] = set()
    pending = list(BaseEvent.__subclasses__())
    while pending:
        cls = pending.pop()
        pending.extend(cls.__subclasses__())
        # events declared inside tests aren't shown in the dashboard
        if hasattr(cls, "category") and cls.__module__.startswith("app."):
            names.add(cls.__name__)
    return names


@pytest.mark.parametrize("locale", ["en", "ru"])
def test_every_event_has_a_title_in_the_dashboard(locale: str) -> None:
    locale_data = json.loads((_LOCALES_DIR / f"{locale}.json").read_text(encoding="utf-8"))

    assert _event_names() - locale_data["eventLog"]["events"].keys() == set()
