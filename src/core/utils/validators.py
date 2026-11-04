import re
from typing import Optional

from src.core.constants import (
    DOMAIN_REGEX,
    INVITE_LINK_PATTERN,
    TAG_REGEX,
    URL_PATTERN,
    USERNAME_PATTERN,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value))


def is_valid_url(text: str) -> bool:
    return bool(URL_PATTERN.match(text))


def is_valid_username(text: str) -> bool:
    return bool(USERNAME_PATTERN.match(text))


def is_valid_domain(text: str) -> bool:
    return bool(DOMAIN_REGEX.match(text))


def is_invite_link(text: str) -> bool:
    return bool(INVITE_LINK_PATTERN.match(text))


def is_valid_tag(text: str) -> bool:
    return bool(TAG_REGEX.fullmatch(text))


def parse_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def is_positive_int(value: Optional[str]) -> bool:
    parsed = parse_int(value)
    return parsed is not None and parsed > 0
