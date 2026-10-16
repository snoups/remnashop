from collections import Counter
from pathlib import Path
from typing import Final

import pytest
from fluent.syntax import FluentParser, ast

_LOCALES: Final[list[Path]] = sorted(
    p for p in (Path(__file__).parents[2] / "assets" / "translations").iterdir() if p.is_dir()
)


@pytest.mark.parametrize("locale_dir", _LOCALES, ids=lambda p: p.name)
def test_no_message_id_is_declared_twice_in_a_locale(locale_dir: Path) -> None:
    parser = FluentParser()
    ids: Counter[str] = Counter()
    for path in sorted(locale_dir.glob("*.ftl")):
        resource = parser.parse(path.read_text(encoding="utf-8"))
        ids.update(
            entry.id.name for entry in resource.body if isinstance(entry, (ast.Message, ast.Term))
        )
    assert [name for name, count in ids.items() if count > 1] == []
