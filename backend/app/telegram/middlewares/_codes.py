from typing import Final, Optional

from aiogram.types import Message, TelegramObject
from loguru import logger

_AD_LINK_PREFIX: Final[str] = "ad_"


def parse_ad_link_code(event: TelegramObject) -> Optional[str]:
    if not isinstance(event, Message) or not event.text:
        return None

    parts = event.text.split()
    if len(parts) <= 1 or parts[0].split("@", 1)[0] != "/start":
        return None

    payload = parts[1]
    if not payload.startswith(_AD_LINK_PREFIX):
        return None

    code = payload[len(_AD_LINK_PREFIX) :]
    if not code:
        return None

    logger.debug(f"Parsed ad link code '{code}' from deep-link payload")
    return code
