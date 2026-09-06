from app.core.enums import Locale
from app.modules.translations.dto import TranslationEntryDto
from app.modules.translations.serializer import find_disallowed_placeable, serialize_to_fluent


def _entry(message_id: str, attribute_id: str, value: str) -> TranslationEntryDto:
    return TranslationEntryDto(
        locale=Locale.EN,
        message_id=message_id,
        attribute_id=attribute_id,
        value=value,
        default_value=value,
    )


def test_serializes_message_with_attribute_only() -> None:
    text = serialize_to_fluent([_entry("command", "menu", "Open the main menu")])

    assert text == "command =\n    .menu = Open the main menu\n"


def test_serializes_plain_message_without_attribute() -> None:
    text = serialize_to_fluent([_entry("welcome", "", "Hello!")])

    assert text == "welcome = Hello!\n"


def test_serializes_message_with_multiple_attributes_in_order() -> None:
    text = serialize_to_fluent(
        [_entry("command", "start", "Start"), _entry("command", "menu", "Menu")]
    )

    assert text == "command =\n    .menu = Menu\n    .start = Start\n"


def test_serializes_message_with_own_value_and_attribute() -> None:
    text = serialize_to_fluent(
        [_entry("command", "", "Commands"), _entry("command", "menu", "Open menu")]
    )

    assert text == "command = Commands\n    .menu = Open menu\n"


def test_serializes_multiple_messages_sorted_by_id() -> None:
    text = serialize_to_fluent([_entry("welcome", "", "Hi"), _entry("command", "menu", "Menu")])

    assert text.index("command") < text.index("welcome")


_ALLOWED = frozenset({"name", "count"})


def test_no_placeable_is_allowed() -> None:
    assert find_disallowed_placeable("Just plain text.", _ALLOWED) is None


def test_known_variable_is_allowed() -> None:
    assert find_disallowed_placeable("Hello, { $name }!", _ALLOWED) is None


def test_multiple_known_variables_are_allowed() -> None:
    assert find_disallowed_placeable("{ $name } has { $count }", _ALLOWED) is None


def test_unknown_variable_is_disallowed() -> None:
    result = find_disallowed_placeable("Hello, { $unknown }!", _ALLOWED)
    assert result is not None
    assert "unknown" in result


def test_message_reference_is_disallowed() -> None:
    assert find_disallowed_placeable("{ some-other-message }", _ALLOWED) is not None


def test_term_reference_is_disallowed() -> None:
    assert find_disallowed_placeable("{ -brand-name }", _ALLOWED) is not None


def test_function_call_is_disallowed() -> None:
    assert find_disallowed_placeable("{ NUMBER($count) }", _ALLOWED) is not None


def test_select_expression_is_disallowed() -> None:
    text = "{ $count -> [one] item *[other] items }"
    assert find_disallowed_placeable(text, _ALLOWED) is not None


def test_engines_own_dollar_brace_token_syntax_is_disallowed() -> None:
    # ${name} (no space) is the render engine's own url_value substitution
    # syntax, not real Fluent -- it must not silently pass here as if it were
    # a valid { $name } reference.
    result = find_disallowed_placeable("${name}", _ALLOWED)
    assert result is not None


def test_unmatched_brace_without_closing_brace_is_not_caught_here() -> None:
    # Known, accepted limitation: this function's job is the placeable-KIND
    # allowlist, not full Fluent syntax validity. Text with an unmatched
    # opening brace and no closing brace parses as Junk but contains no
    # matching "}", so it falls through to None here. It's still caught by
    # the separate FluentBundle.check_messages() compile check the caller
    # (UpdateDialogTextUseCase) runs on the full candidate text afterward.
    assert find_disallowed_placeable("Hi { unterminated", _ALLOWED) is None
