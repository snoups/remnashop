import re
from collections import defaultdict
from collections.abc import Callable
from typing import Final, Optional

from fluent.syntax import FluentParser
from fluent.syntax.ast import (
    Junk,
    Message,
    Pattern,
    Placeable,
    SelectExpression,
    StringLiteral,
    VariableReference,
)
from fluent_compiler.bundle import FluentBundle
from loguru import logger

from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.utils.telegram_text import validate_telegram_html
from app.modules.translations.dto import TranslationEntryDto


def split_message_key(key: str) -> tuple[str, str]:
    """Split a Fluent lookup key into the (message_id, attribute_id) pair a
    translations row is keyed by. `btn-menu.trial` is message `btn-menu`'s
    `trial` attribute; storing it whole as a message id produces a row that
    shadows the real one and serializes to invalid Fluent, since a message id
    cannot contain a dot."""
    message_id, separator, attribute_id = key.rpartition(".")
    return (message_id, attribute_id) if separator else (key, "")


def join_message_key(message_id: str, attribute_id: str) -> str:
    return f"{message_id}.{attribute_id}" if attribute_id else message_id


# Fluent reads an indented line starting with one of these as a variant key,
# default variant or attribute, and a premium emoji's `[glyph](emoji:id)` starts with one.
_LINE_START_SPECIAL: Final[frozenset[str]] = frozenset("[*.")


def _escape_line_start(line: str) -> str:
    # Fluent reads past the indent, so the first visible character is the one that counts;
    # a string-literal placeable renders as the bare character
    body = line.lstrip(" ")
    indent = line[: len(line) - len(body)]
    return f'{indent}{{"{body[0]}"}}{body[1:]}' if body[:1] in _LINE_START_SPECIAL else line


# Fluent has no empty value: `key =` alone is a syntax error that takes the
# whole message down, so an unset icon or a banner-only window's blank caption
# is written as an empty string literal.
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
    # Inside a placeable a line start is select syntax (`[key]`, `*[other]`), not text.
    # No allowed placeable holds a brace in a string literal, so counting is enough.
    first, *rest = value.split("\n")
    lines = [first]
    depth = first.count("{") - first.count("}")
    for line in rest:
        lines.append(line if depth > 0 else _escape_line_start(line))
        depth += line.count("{") - line.count("}")
    return f"\n{indent}".join(lines)


def fluent_value_source(value: str) -> str:
    """The right-hand side of `key = ...` as serialize_to_fluent writes a
    message-level value."""
    return _block(value, "    ")


# Ids are written unescaped: one that isn't an identifier would start a new
# top-level entry and shadow a real message, so such a row is dropped.
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


# Window bodies and fragments are sent with parse_mode=HTML; other keys are plain text.
_HTML_KEY_PREFIXES: Final[tuple[str, ...]] = ("msg-", "frg-")


def assert_valid_bot_html(message_id: str, value: str) -> None:
    if message_id.startswith(_HTML_KEY_PREFIXES):
        validate_telegram_html(value, code=ErrorCode.TRANSLATION_HTML_INVALID)


# Telegram rejects a multi-line bot command description; the command menu is
# repushed on every edit.
_SINGLE_LINE_MESSAGE_IDS: Final[frozenset[str]] = frozenset({"command"})


def assert_translation_value(message_id: str, value: str, default_value: str) -> None:
    """A translator may rephrase a string, reorder its variables and rewrite its
    plural or value variants, but not reach for anything the shipped string
    doesn't use: only the variables of `default_value`, selects over them and
    string literals pass."""
    if "\n" in value and message_id in _SINGLE_LINE_MESSAGE_IDS:
        raise ValidationError(
            "Bot command descriptions cannot contain newlines",
            code=ErrorCode.TRANSLATION_HAS_NEWLINES,
        )
    allowed_variables = placeable_variables(default_value)
    disallowed = _find_disallowed(
        value, lambda expression: _check_translation_expression(expression, allowed_variables)
    )
    if disallowed is not None:
        raise ValidationError(disallowed, code=ErrorCode.TRANSLATION_VARIABLE_NOT_ALLOWED)


def _value_patterns(text: str) -> Optional[list[Pattern]]:
    """The patterns of a stored value, wrapped exactly as serialize_to_fluent
    writes it; None when it parses as Junk."""
    parsed = FluentParser().parse("placeholder-id = " + _block(text, "    "))
    if parsed.body and isinstance(parsed.body[0], Junk):
        return None
    patterns: list[Pattern] = []
    for entry in parsed.body:
        if not isinstance(entry, Message):
            continue
        if entry.value is not None:
            patterns.append(entry.value)
        patterns.extend(attribute.value for attribute in entry.attributes)
    return patterns


def _placeable_expressions(pattern: Pattern) -> list[object]:
    return [element.expression for element in pattern.elements if isinstance(element, Placeable)]


def placeable_variables(text: str) -> frozenset[str]:
    names: set[str] = set()

    def collect(expression: object) -> None:
        if isinstance(expression, VariableReference):
            names.add(expression.id.name)
        elif isinstance(expression, SelectExpression):
            collect(expression.selector)
            for variant in expression.variants:
                for inner in _placeable_expressions(variant.value):
                    collect(inner)

    for pattern in _value_patterns(text) or []:
        for expression in _placeable_expressions(pattern):
            collect(expression)
    return frozenset(names)


def _check_translation_expression(
    expression: object, allowed_variables: frozenset[str]
) -> Optional[str]:
    if isinstance(expression, StringLiteral):
        return None
    if isinstance(expression, SelectExpression):
        if not isinstance(expression.selector, VariableReference):
            return "Disallowed Fluent expression: a select over anything but a variable"
        for inner in [expression.selector] + [
            nested
            for variant in expression.variants
            for nested in _placeable_expressions(variant.value)
        ]:
            result = _check_translation_expression(inner, allowed_variables)
            if result is not None:
                return result
        return None
    return _check_placeable_expression(expression, allowed_variables)


def _check_placeable_expression(
    expression: object, allowed_variables: frozenset[str]
) -> Optional[str]:
    # the serializer's escapes: a line start (_escape_line_start) or an empty value
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
    """The reason the first disallowed placeable in a dialog text is refused, or
    None. Only a bare `{ $name }` with `name` in `allowed_variables` passes;
    message and term references, functions and selects never do. A value that
    parses as Junk and holds both braces is refused too."""
    return _find_disallowed(
        text, lambda expression: _check_placeable_expression(expression, allowed_variables)
    )


def _find_disallowed(text: str, check: Callable[[object], Optional[str]]) -> Optional[str]:
    patterns = _value_patterns(text)
    if patterns is None:
        # Braces in Junk are most likely an inline select expression: Fluent wants
        # each variant on its own indented line, so a one-line attempt parses as
        # Junk instead of a SelectExpression and would otherwise pass as "no
        # placeables found".
        if "{" in text and "}" in text:
            return "Disallowed Fluent expression: malformed or complex expression"
        # an unmatched brace ("{ unterminated") falls through to None: this only
        # allowlists placeable kinds, the caller's FluentBundle.check_messages()
        # catches broken syntax
        return None
    for pattern in patterns:
        for expression in _placeable_expressions(pattern):
            result = check(expression)
            if result is not None:
                return result
    return None


def assert_fluent_compiles(locale: Locale, text: str) -> None:
    bundle = FluentBundle.from_string(locale.value, text=text)  # type: ignore[no-untyped-call]
    errors = bundle.check_messages()
    if errors:
        raise ValidationError(
            f"Invalid Fluent syntax in {locale.value}: {errors[0][1]}",
            code=ErrorCode.FLUENT_SYNTAX_INVALID,
        )
