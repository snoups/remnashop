import ast
from collections import defaultdict
from pathlib import Path
from typing import Final

import app

_APP_DIR: Final[Path] = Path(app.__file__).parent
_MODULES_DIR: Final[Path] = _APP_DIR / "modules"


def _imported_from_outside() -> dict[str, set[str]]:
    used: dict[str, set[str]] = defaultdict(set)
    for path in _APP_DIR.rglob("*.py"):
        parts = path.relative_to(_APP_DIR).parts
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            target = node.module.split(".")
            if len(target) != 3 or target[:2] != ["app", "modules"]:
                continue
            if parts[:2] == ("modules", target[2]):
                continue
            used[target[2]].update(alias.name for alias in node.names)
    return used


def test_module_interfaces_export_only_what_other_packages_import() -> None:
    used = _imported_from_outside()
    unused = [
        f"{init.parent.name}.{alias.name}"
        for init in sorted(_MODULES_DIR.glob("*/__init__.py"))
        for node in ast.parse(init.read_text()).body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name not in used[init.parent.name]
    ]
    assert unused == []
