from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class BotCommand:
    command: str
    description_key: str


# Source of truth for which slash commands the bot actually handles -- keep in
# sync by hand with app/telegram/routers/**/handlers.py's Command(...) filters
# whenever one is added or removed.
#
# description_key resolves against backend/assets/translations/<locale>/commands.ftl
# (Fluent message "command" with one attribute per slash command), via
# command_translations.build_command_translator_hub -- never admin-editable.
BOT_COMMANDS: Final[tuple[BotCommand, ...]] = (
    BotCommand(command="start", description_key="command.start"),
    # Telegram Stars terms require bots taking payments to answer /paysupport
    BotCommand(command="paysupport", description_key="command.paysupport"),
)
