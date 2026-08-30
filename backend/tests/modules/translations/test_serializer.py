from app.core.enums import Locale
from app.modules.translations.dto import TranslationEntryDto
from app.modules.translations.serializer import serialize_to_fluent


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
