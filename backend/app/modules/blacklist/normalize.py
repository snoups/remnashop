import re
from typing import Final, Optional
from urllib.parse import urlsplit

from app.core.enums import BlacklistKind

_MAX_VALUE_LEN: Final[int] = 254
_NON_DIGIT_RE: Final[re.Pattern[str]] = re.compile(r"\D+")
# local@domain.tld: a dotted domain with no empty labels
_EMAIL_RE: Final[re.Pattern[str]] = re.compile(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+")
_GITHUB_HOSTS: Final[frozenset[str]] = frozenset({"github.com", "raw.githubusercontent.com"})


def normalize_identity(kind: BlacklistKind, raw: str) -> Optional[str]:
    trimmed = raw.strip()
    if not trimmed or len(trimmed) > _MAX_VALUE_LEN:
        return None

    if kind is BlacklistKind.TELEGRAM_ID:
        digits = _NON_DIGIT_RE.sub("", trimmed).lstrip("0")
        return digits or None

    lowered = trimmed.lower()
    return lowered if _EMAIL_RE.fullmatch(lowered) else None


def removal_key(kind: BlacklistKind, raw: str) -> Optional[str]:
    # matches how entries are stored without re-validating the format, so an
    # entry saved under a looser rule can still be removed
    if kind is BlacklistKind.TELEGRAM_ID:
        return normalize_identity(kind, raw)
    return raw.strip().lower() or None


def derive_source_name(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or url).removeprefix("www.")
    segments = [segment for segment in parts.path.split("/") if segment]
    if host in _GITHUB_HOSTS and len(segments) >= 2:
        return f"{segments[0]}/{segments[1]}"
    return f"{host}/{segments[-1]}" if segments else host
