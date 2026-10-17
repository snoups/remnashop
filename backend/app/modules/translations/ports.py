from typing import Protocol

from app.core.enums import Locale


class DefaultBannerSeed(Protocol):
    # puts the shipped banner in place for a locale that has none
    async def ensure(self, locale: Locale) -> None: ...


class BotCommandsSync(Protocol):
    # re-sends the bot's command menu after a translation or locale change;
    # both are no-ops while no bot is configured, push() is False on failure
    async def push(self) -> bool: ...

    async def drop_locale(self, locale: Locale) -> None: ...
