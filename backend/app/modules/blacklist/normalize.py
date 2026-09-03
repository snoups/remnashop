import re
from typing import Final, Optional

from app.core.enums import BlacklistKind

_MAX_VALUE_LEN: Final[int] = 254
_NON_DIGIT_RE: Final[re.Pattern[str]] = re.compile(r"\D+")
_EMAIL_RE: Final[re.Pattern[str]] = re.compile(r"[^\s@]+@[^\s@]+")


def normalize_identity(kind: BlacklistKind, raw: str) -> Optional[str]:
    trimmed = raw.strip()
    if not trimmed or len(trimmed) > _MAX_VALUE_LEN:
        return None

    if kind is BlacklistKind.TELEGRAM_ID:
        digits = _NON_DIGIT_RE.sub("", trimmed).lstrip("0")
        return digits or None

    lowered = trimmed.lower()
    return lowered if _EMAIL_RE.fullmatch(lowered) else None
