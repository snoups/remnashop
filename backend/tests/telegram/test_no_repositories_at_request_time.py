import ast
from pathlib import Path
from typing import Final

import app.telegram

_TELEGRAM_DIR: Final[Path] = Path(app.telegram.__file__).parent
# startup loading and DI wiring: these run before any update arrives, or only
# hand usecases a repository (settings_cache.py swaps in caching subclasses)
_STARTUP_FILES: Final[frozenset[str]] = frozenset(
    {"i18n.py", "lifespan.py", "dialogs/config_cache.py", "dialogs/di.py", "settings_cache.py"}
)


def test_bot_reads_go_through_usecases() -> None:
    # import-linter can't see this: repositories are exported from each
    # module's __init__.py next to its usecases
    offenders = [
        f"{path.relative_to(_TELEGRAM_DIR)}: {alias.name}"
        for path in sorted(_TELEGRAM_DIR.rglob("*.py"))
        if str(path.relative_to(_TELEGRAM_DIR)) not in _STARTUP_FILES
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name.endswith("Repository")
    ]
    assert offenders == []
