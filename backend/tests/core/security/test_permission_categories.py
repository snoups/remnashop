import json
import re
from pathlib import Path
from typing import Final

import pytest

import app as app_package
from app.core.security.permissions import PERMISSION_METADATA

_LOCALES_DIR: Final[Path] = (
    Path(app_package.__file__).parents[2] / "frontend" / "src" / "shared" / "i18n" / "locales"
)


def _category_key(resource: str) -> str:
    # mirrors the dashboard's resourceCategoryKey: bot_settings -> botSettings
    return re.sub(r"_([a-z])", lambda match: match.group(1).upper(), resource)


@pytest.mark.skipif(not _LOCALES_DIR.exists(), reason="frontend sources not present")
@pytest.mark.parametrize("locale", ["en", "ru"])
def test_every_permission_resource_has_a_category_label(locale: str) -> None:
    labels = json.loads((_LOCALES_DIR / f"{locale}.json").read_text())["permissionCategories"]
    keys = {_category_key(meta.resource) for meta in PERMISSION_METADATA.values()}

    assert sorted(keys - set(labels)) == []
    assert sorted(set(labels) - keys) == []
