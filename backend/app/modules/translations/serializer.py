import re
from collections import defaultdict
from typing import Final, Optional

from loguru import logger

from app.modules.translations.dto import TranslationEntryDto


def split_message_key(key: str) -> tuple[str, str]:
    """Split a Fluent lookup key into the (message_id, attribute_id) pair a
    translations row is keyed by. `btn-menu.trial` is message `btn-menu`'s
    `trial` attribute -- storing it whole as a message id produces a row that
    shadows the real one and serializes to invalid Fluent, since a message id
    cannot contain a dot."""
    message_id, separator, attribute_id = key.rpartition(".")
    return (message_id, attribute_id) if separator else (key, "")


def join_message_key(message_id: str, attribute_id: str) -> str:
    return f"{message_id}.{attribute_id}" if attribute_id else message_id


# Fluent reads an indented line starting with one of these as a variant key,
# default variant or attribute -- a premium emoji's `[glyph](emoji:id)` among them.
_LINE_START_SPECIAL: Final[frozenset[str]] = frozenset("[*.")


def _escape_line_start(line: str) -> str:
    # a string-literal placeable renders as the bare character
    return f'{{"{line[0]}"}}{line[1:]}' if line[:1] in _LINE_START_SPECIAL else line


# Fluent has no empty value -- `key =` alone is a syntax error that takes the
# whole message down. An unset icon or a banner-only window's blank caption is
# written as an empty string literal instead.
_EMPTY_VALUE: Final[str] = '{ "" }'


def strip_serializer_escapes(text: str) -> str:
    """Drop the bidi isolation marks Fluent puts around the serializer's own
    placeables: an escaped line start (so a rendered `[glyph](emoji:id)` is
    contiguous again) and an empty value (so it renders as nothing at all)."""
    text = text.replace("\u2068\u2069", "")
    for char in _LINE_START_SPECIAL:
        text = text.replace(f"\u2068{char}\u2069", char)
    return text


def _block(value: str, indent: str) -> str:
    # A Fluent pattern continues onto the next line only while that line is
    # indented, so a stored newline has to carry the indent with it. Fluent
    # strips the common indent back off when it parses the value. The first
    # line sits right after `=`, where these characters are plain text.
    if not value:
        return _EMPTY_VALUE
    first, *rest = value.split("\n")
    return f"\n{indent}".join([first, *map(_escape_line_start, rest)])


# Ids are written unescaped -- one that isn't an identifier would start a new
# top-level entry and shadow a real message, so such a row is dropped instead.
_FLUENT_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]*")


def serialize_to_fluent(entries: list[TranslationEntryDto]) -> str:
    by_message: dict[str, list[TranslationEntryDto]] = defaultdict(list)
    for entry in entries:
        ids = (entry.message_id, entry.attribute_id) if entry.attribute_id else (entry.message_id,)
        if not all(_FLUENT_IDENTIFIER_RE.fullmatch(part) for part in ids):
            logger.warning(f"Skipping translation row with an invalid Fluent id: {ids!r}")
            continue
        by_message[entry.message_id].append(entry)

    lines: list[str] = []
    for message_id in sorted(by_message):
        group = sorted(by_message[message_id], key=lambda entry: entry.attribute_id)
        own_value = next((entry.value for entry in group if entry.attribute_id == ""), None)
        lines.append(
            f"{message_id} = {_block(own_value, '    ')}"
            if own_value is not None
            else f"{message_id} ="
        )
        for entry in group:
            if entry.attribute_id:
                lines.append(f"    .{entry.attribute_id} = {_block(entry.value, '        ')}")

    return "\n".join(lines) + "\n"


def contains_placeable(text: str) -> bool:
    # Lazy import -- fluent.syntax ships with fluent_compiler, which lives
    # under the `telegram` extra.
    from fluent.syntax import FluentParser  # noqa: PLC0415
    from fluent.syntax.ast import Message, Pattern, Placeable  # noqa: PLC0415

    patterns: list[Pattern] = []
    for entry in FluentParser().parse(text).body:
        if not isinstance(entry, Message):
            continue
        if entry.value is not None:
            patterns.append(entry.value)
        patterns.extend(attribute.value for attribute in entry.attributes)

    return any(
        isinstance(element, Placeable) for pattern in patterns for element in pattern.elements
    )


def _check_placeable_expression(
    expression: object, allowed_variables: frozenset[str]
) -> Optional[str]:
    """Check a single placeable expression. Helper for find_disallowed_placeable."""
    from fluent.syntax.ast import StringLiteral, VariableReference  # noqa: PLC0415

    # the serializer's own escapes: a line start (_escape_line_start) or an empty value
    if isinstance(expression, StringLiteral) and (
        expression.value in _LINE_START_SPECIAL or expression.value == ""
    ):
        return None
    if isinstance(expression, VariableReference):
        if expression.id.name in allowed_variables:
            return None
        return f"Unknown variable: {expression.id.name}"
    return f"Disallowed Fluent expression: {type(expression).__name__}"


def find_disallowed_placeable(text: str, allowed_variables: frozenset[str]) -> Optional[str]:
    """Check a candidate dialog text value for Fluent placeables: a bare
    `{ $name }` variable reference is allowed only when `name` is in
    `allowed_variables` (the catalog's registered variable set); every other
    kind of placeable (message references, term references, function calls,
    select expressions) is rejected regardless of what it contains. Returns a
    human-readable reason for the first disallowed placeable found, or None if
    the value contains only allowed ones (including none at all).

    A literal `{` or `}` cannot appear in dialog text: any value that fails to
    parse as a clean Pattern (Junk) and contains both braces is rejected,
    matching Fluent's own grammar and the general editor's effective behavior.
    """
    # Lazy import -- fluent.syntax ships with fluent_compiler, which lives
    # under the `telegram` extra.
    from fluent.syntax import FluentParser  # noqa: PLC0415
    from fluent.syntax.ast import (  # noqa: PLC0415
        Junk,
        Message,
        Pattern,
        Placeable,
    )

    # wrapped exactly as serialize_to_fluent writes it
    wrapped = "placeholder-id = " + _block(text, "    ")
    parsed = FluentParser().parse(wrapped)

    # If parsing produced Junk, check if text contains placeable-like syntax
    if parsed.body and isinstance(parsed.body[0], Junk):
        # Text with braces might be a malformed placeable (e.g. select expression).
        # Fluent's select-expression grammar requires each variant to start its own
        # indented line, so a single-line inline attempt (as the original brief's code
        # would have produced) fails to parse as a clean SelectExpression node and
        # instead produces Junk -- this multi-line wrapping approach and the
        # Junk-handling below exist specifically to catch that case rather than
        # silently letting it through as "no placeables found."
        if "{" in text and "}" in text:
            return "Disallowed Fluent expression: malformed or complex expression"
        # Note: text with an unmatched brace (e.g. "{ unterminated") falls through
        # to None here rather than being flagged -- this function's job is the
        # placeable-kind allowlist, not full Fluent syntax validity; a genuinely
        # malformed value is still caught by the separate FluentBundle.check_messages()
        # compile check the caller runs afterward.
        return None

    patterns: list[Pattern] = []
    for entry in parsed.body:
        if not isinstance(entry, Message):
            continue
        if entry.value is not None:
            patterns.append(entry.value)
        patterns.extend(attribute.value for attribute in entry.attributes)

    for pattern in patterns:
        for element in pattern.elements:
            if not isinstance(element, Placeable):
                continue
            result = _check_placeable_expression(element.expression, allowed_variables)
            if result is not None:
                return result
    return None
