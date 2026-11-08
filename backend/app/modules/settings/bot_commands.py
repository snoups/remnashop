from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class BotCommand:
    command: str
    description_key: str


# keep in sync by hand with the Command(...) filters in app/telegram/routers/;
# description_key is an attribute of commands.ftl's "command" message
BOT_COMMANDS: Final[tuple[BotCommand, ...]] = (
    BotCommand(command="start", description_key="command.start"),
    # Telegram Stars terms require bots taking payments to answer /paysupport
    BotCommand(command="paysupport", description_key="command.paysupport"),
    BotCommand(command="terms", description_key="command.terms"),
)
