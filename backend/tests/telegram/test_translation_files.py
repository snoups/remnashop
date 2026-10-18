from collections import Counter
from pathlib import Path
from typing import Final

import pytest
from fluent.syntax import FluentParser, Visitor, ast
from fluent_compiler.bundle import FluentBundle

from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.utils.telegram_text import validate_telegram_html
from app.modules.translations import strip_serializer_escapes
from tests.seeded_translations import seeded_fluent_source

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


class _Variables(Visitor):
    def __init__(self) -> None:
        super().__init__()
        self.names: set[str] = set()

    def visit_VariableReference(self, node: ast.VariableReference) -> None:  # noqa: N802
        self.names.add(node.id.name)


@pytest.mark.parametrize("locale_dir", _LOCALES, ids=lambda p: p.name)
def test_shipped_window_texts_are_valid_html(locale_dir: Path) -> None:
    # Every variable gets a placeholder value, so any error left is a real one;
    # selectors take their default variant.
    authored = "\n".join(p.read_text(encoding="utf-8") for p in sorted(locale_dir.glob("*.ftl")))
    messages = [
        entry
        for entry in FluentParser().parse(authored).body
        if isinstance(entry, ast.Message)
        and entry.value is not None
        and entry.id.name.startswith(("msg-", "frg-"))
    ]
    assert messages
    source = seeded_fluent_source(Locale(locale_dir.name))
    bundle = FluentBundle.from_string(locale_dir.name, text=source)  # type: ignore[no-untyped-call]
    for message in messages:
        variables = _Variables()
        variables.visit(message)
        text, errors = bundle.format(message.id.name, dict.fromkeys(variables.names, "x"))
        assert errors == [], message.id.name
        validate_telegram_html(
            strip_serializer_escapes(text).replace("\u2068", "").replace("\u2069", ""),
            code=ErrorCode.TRANSLATION_HTML_INVALID,
        )
