from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class BotCommand:
    command: str
    description_key: str


# The slash commands the bot handles; keep in sync by hand with the
# Command(...) filters in app/telegram/routers/**/handlers.py.
#
# description_key resolves against backend/assets/translations/<locale>/commands.ftl
# (message "command", one attribute per command) through the bot's translator
# hub (app/telegram/i18n.py); not admin-editable.
BOT_COMMANDS: Final[tuple[BotCommand, ...]] = (
    BotCommand(command="start", description_key="command.start"),
    # Telegram Stars terms require bots taking payments to answer /paysupport
    BotCommand(command="paysupport", description_key="command.paysupport"),
)
