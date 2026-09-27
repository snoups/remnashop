import pytest
from fluentogram.exceptions import KeyNotFoundError

from app.core.enums import Locale
from app.modules.settings.command_translations import build_command_translator_hub

_EN_TEXT = "command =\n    .start = Open the main menu\n"


def test_resolves_configured_command_description() -> None:
    hub = build_command_translator_hub([Locale.EN], {Locale.EN: _EN_TEXT}, Locale.EN)

    runner = hub.get_translator_by_locale(Locale.EN.value)

    assert runner.get("command.start") == "Open the main menu"


def test_missing_key_raises_key_not_found() -> None:
    hub = build_command_translator_hub([Locale.EN], {Locale.EN: _EN_TEXT}, Locale.EN)

    runner = hub.get_translator_by_locale(Locale.EN.value)

    with pytest.raises(KeyNotFoundError):
        runner.get("command.missing")
