from app.modules.settings.bot_commands import BOT_COMMANDS


def test_bot_commands_has_unique_command_names() -> None:
    names = [item.command for item in BOT_COMMANDS]
    assert len(names) == len(set(names))


def test_menu_command_is_registered() -> None:
    names = {item.command for item in BOT_COMMANDS}
    assert "menu" in names
