import html
import re
import unicodedata
from typing import Final, Optional

MAX_NAME_LENGTH: Final[int] = 32

_HTML_TAG_RE: Final[re.Pattern[str]] = re.compile(r"<[^>]*>")
_URL_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(?:https?://|www\.|tg://|t\.me/|telegram\.me/|joinchat/)\S+"
)
# whitelist, not a blacklist: none of these can form Fluent placeables ({ }),
# HTML (< > &), premium-emoji markup ([x](emoji:1)) or ${var} tokens
_ALLOWED_SYMBOLS: Final[frozenset[str]] = frozenset("_-.'")


def clean_display_name(name: Optional[str]) -> str:
    """Empty when nothing survives; the caller decides the fallback."""
    text = unicodedata.normalize("NFKC", html.unescape(name or ""))
    text = _URL_RE.sub("", _HTML_TAG_RE.sub("", text))
    # letters, digits and combining marks (Indic/Thai vowels are marks);
    # Cf (bidi overrides, zero-width joiners) and symbols/emoji drop out
    kept = "".join(
        char
        for char in text
        if unicodedata.category(char)[0] in "LNM" or char in _ALLOWED_SYMBOLS or char.isspace()
    )
    cleaned = " ".join(kept.split())[:MAX_NAME_LENGTH].strip()
    # "." or "-" alone is how Telegram users leave their name blank
    if not any(unicodedata.category(char)[0] in "LN" for char in cleaned):
        return ""
    return cleaned
