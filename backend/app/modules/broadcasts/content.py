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
# the longest a variable renders to: a text is checked against Telegram's limit with
# every variable at this length, and a longer value is cut to it when sent
VARIABLE_MAX_LENGTHS: Final[Mapping[str, int]] = {
    "name": 64,
    "username": 33,
    "plan": 64,
    "expire_date": 10,
    "days_left": 6,
    "bonus_days": 6,
    "points": 13,
    "promocode": 64,
}
_CUT_MARK: Final[str] = "…"


def used_variables(text: str) -> set[str]:
    return set(VARIABLE_RE.findall(text))


def longest_text(text: str) -> str:
    """The text with every variable at its longest, for the length check."""
    return VARIABLE_RE.sub(
        lambda m: "x" * VARIABLE_MAX_LENGTHS.get(m.group(1), len(EMPTY_VALUE)), text
    )


def _fit(name: str, value: str) -> str:
    limit = VARIABLE_MAX_LENGTHS.get(name)
    if limit is None or len(value) <= limit:
        return value
    return value[: limit - len(_CUT_MARK)] + _CUT_MARK


def render_text(text: str, values: Mapping[str, str]) -> str:
    rendered = PREMIUM_EMOJI_RE.sub(r'<tg-emoji emoji-id="\2">\1</tg-emoji>', text)
    return VARIABLE_RE.sub(
        lambda m: html.escape(_fit(m.group(1), values.get(m.group(1)) or EMPTY_VALUE)), rendered
    )
