import pytest
from fluent.syntax import FluentParser
from fluent.syntax.ast import Junk, Message
from fluent_compiler.bundle import FluentBundle

from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.translations.dto import TranslationEntryDto
from app.modules.translations.serializer import (
    assert_valid_bot_html,
    find_disallowed_placeable,
    serialize_to_fluent,
    split_message_key,
    strip_serializer_escapes,
)
from tests.seeded_translations import seeded_fluent_source


def _entry(message_id: str, attribute_id: str, value: str) -> TranslationEntryDto:
    return TranslationEntryDto(
        locale=Locale.EN,
        message_id=message_id,
        attribute_id=attribute_id,
        value=value,
        default_value=value,
    )


def test_skips_rows_whose_ids_are_not_fluent_identifiers() -> None:
    text = serialize_to_fluent(
        [
            _entry("msg-dialog-custom-a=x\nmsg-main-menu=INJECTED\n z", "", "Button"),
            _entry("msg-main-menu", "bad id", "x"),
            _entry("msg-main-menu", "", "Real"),
        ]
    )

    assert text == "msg-main-menu = Real\n"
    bundle = FluentBundle.from_string("en", text=text)  # type: ignore[no-untyped-call]
    assert bundle.format("msg-main-menu")[0] == "Real"


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
    # ${name} is url_value's substitution, not Fluent, and must not pass
    # for a { $name } reference
    result = find_disallowed_placeable("${name}", _ALLOWED)
    assert result is not None


def test_unmatched_brace_without_closing_brace_is_not_caught_here() -> None:
    # only placeable kinds are checked here; the caller's
    # FluentBundle.check_messages() catches the broken syntax

    assert find_disallowed_placeable("Hi { unterminated", _ALLOWED) is None


def test_premium_emoji_at_text_start_is_allowed() -> None:
    assert find_disallowed_placeable("[🌊](emoji:5) Hi, { $name }!", _ALLOWED) is None


@pytest.mark.parametrize(
    "line", ["[🌊](emoji:5) Hi, { $name }!", "* star { $name }", ".dot { $name }"]
)
def test_special_char_at_continuation_line_start_is_allowed(line: str) -> None:
    assert find_disallowed_placeable(f"First\n{line}", _ALLOWED) is None


def test_empty_attribute_value_round_trips() -> None:
    text = serialize_to_fluent([_entry("btn", "a", "Label"), _entry("btn", "a-icon-id", "")])
    bundle = FluentBundle.from_string("en", text=text)

    assert bundle.check_messages() == []
    assert bundle.format("btn.a")[0] == "Label"
    assert strip_serializer_escapes(bundle.format("btn.a-icon-id")[0]) == ""


@pytest.mark.parametrize("line", ["[🌊](emoji:5) x", "* star", ".dot"])
def test_special_char_at_continuation_line_start_round_trips(line: str) -> None:
    value = f"First\n{line}"
    bundle = FluentBundle.from_string("en", text=serialize_to_fluent([_entry("msg", "", value)]))

    assert bundle.check_messages() == []
    assert strip_serializer_escapes(bundle.format("msg")[0]) == value


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("btn-menu.trial", ("btn-menu", "trial")),
        ("msg-main-menu", ("msg-main-menu", "")),
        ("msg-dialog-custom-3f9a", ("msg-dialog-custom-3f9a", "")),
        ("platform-icon.ios", ("platform-icon", "ios")),
    ],
)
def test_split_message_key(key: str, expected: tuple[str, str]) -> None:
    assert split_message_key(key) == expected


def test_an_indented_line_starting_with_a_dot_stays_in_the_value() -> None:
    text = serialize_to_fluent([_entry("msg-a", "", "Hello\n  .note = x")])
    value, errors = FluentBundle.from_string("en", text).format("msg-a")
    assert not errors
    assert strip_serializer_escapes(value).endswith(".note = x")


def test_general_editor_checks_html_for_msg_and_frg_only() -> None:
    with pytest.raises(ValidationError) as exc:
        assert_valid_bot_html("msg-x", "<div>")
    assert exc.value.code == ErrorCode.TRANSLATION_HTML_INVALID
    with pytest.raises(ValidationError):
        assert_valid_bot_html("frg-x", "<b>")
    assert_valid_bot_html("btn-x", "<3")


@pytest.mark.parametrize("locale", [Locale.EN, Locale.RU])
def test_every_seeded_message_survives_the_database_round_trip(locale: Locale) -> None:
    source = seeded_fluent_source(locale)
    resource = FluentParser().parse(source)

    assert [entry.content[:80] for entry in resource.body if isinstance(entry, Junk)] == []
    bundle = FluentBundle.from_string(locale.value, text=source)  # type: ignore[no-untyped-call]
    assert bundle.check_messages() == []
    for entry in resource.body:
        assert isinstance(entry, Message)
        if entry.value is not None:
            assert bundle.format(entry.id.name)[0]
