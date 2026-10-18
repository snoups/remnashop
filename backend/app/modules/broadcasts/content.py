import html
import re
from collections.abc import Mapping
from typing import Final

from app.core.utils.telegram_text import PREMIUM_EMOJI_RE

VARIABLE_RE: Final[re.Pattern[str]] = re.compile(r"\{\s*\$([a-z_]+)\s*\}")
BROADCAST_VARIABLES: Final[frozenset[str]] = frozenset(
    {"name", "username", "plan", "expire_date", "days_left", "bonus_days", "points", "promocode"}
)
CHANNEL_VARIABLES: Final[frozenset[str]] = frozenset({"promocode"})
EMPTY_VALUE: Final[str] = "—"


def used_variables(text: str) -> set[str]:
    return set(VARIABLE_RE.findall(text))


def render_text(text: str, values: Mapping[str, str]) -> str:
    rendered = PREMIUM_EMOJI_RE.sub(r'<tg-emoji emoji-id="\2">\1</tg-emoji>', text)
    return VARIABLE_RE.sub(lambda m: html.escape(values.get(m.group(1)) or EMPTY_VALUE), rendered)
