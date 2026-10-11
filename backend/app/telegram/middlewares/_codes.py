from typing import Final, Optional

from aiogram.types import Message, TelegramObject
from loguru import logger

_AD_LINK_PREFIX: Final[str] = "ad_"
_REFERRAL_PREFIX: Final[str] = "ref_"
_WEBAUTH_PREFIX: Final[str] = "webauth_"


def _parse_start_code(event: TelegramObject, prefix: str) -> Optional[str]:
    if not isinstance(event, Message) or not event.text:
        return None

    parts = event.text.split()
    if len(parts) <= 1 or parts[0].split("@", 1)[0] != "/start":
        return None

    payload = parts[1]
    if not payload.startswith(prefix):
        return None

    code = payload[len(prefix) :]
    if not code:
        return None

    logger.debug(f"Parsed '{prefix}' code '{code}' from deep-link payload")
    return code


def parse_ad_link_code(event: TelegramObject) -> Optional[str]:
    return _parse_start_code(event, _AD_LINK_PREFIX)


def parse_referral_code(event: TelegramObject) -> Optional[str]:
    return _parse_start_code(event, _REFERRAL_PREFIX)


def parse_webauth_token(event: TelegramObject) -> Optional[str]:
    return _parse_start_code(event, _WEBAUTH_PREFIX)
