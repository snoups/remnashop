import html
import re
from collections.abc import Mapping
from html.parser import HTMLParser
from typing import Final, Optional

from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.utils.telegram_text import PREMIUM_EMOJI_RE

VARIABLE_RE: Final[re.Pattern[str]] = re.compile(r"\{\s*\$([a-z_]+)\s*\}")
BROADCAST_VARIABLES: Final[frozenset[str]] = frozenset(
    {"name", "username", "plan", "expire_date", "days_left", "bonus_days", "points", "promocode"}
)
CHANNEL_VARIABLES: Final[frozenset[str]] = frozenset({"promocode"})
EMPTY_VALUE: Final[str] = "—"
_ALLOWED_TAGS: Final[frozenset[str]] = frozenset(
    {
        "b",
        "strong",
        "i",
        "em",
        "u",
        "ins",
        "s",
        "strike",
        "del",
        "a",
        "code",
        "pre",
        "blockquote",
        "tg-spoiler",
    }
)
_URL_SCHEMES: Final[tuple[str, ...]] = ("https://", "http://", "tg://")


def used_variables(text: str) -> set[str]:
    return set(VARIABLE_RE.findall(text))


def _invalid(reason: str) -> ValidationError:
    return ValidationError(f"Invalid HTML: {reason}", code=ErrorCode.BROADCAST_HTML_INVALID)


class _TagChecker(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: list[str] = []

    def handle_data(self, data: str) -> None:
        if "<" in data:
            raise _invalid("bare < in text data must be escaped as &lt;")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag not in _ALLOWED_TAGS:
            raise _invalid(f"<{tag}> is not supported")
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if not href.startswith(_URL_SCHEMES):
                raise _invalid("link must start with https://, http:// or tg://")
        self.stack.append(tag)

    def handle_comment(self, data: str) -> None:
        raise _invalid("comments are not supported")

    def handle_decl(self, decl: str) -> None:
        raise _invalid("declarations are not supported")

    def handle_pi(self, data: str) -> None:
        raise _invalid("processing instructions are not supported")

    def unknown_decl(self, data: str) -> None:
        raise _invalid("declarations are not supported")

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack[-1] != tag:
            raise _invalid(f"unexpected </{tag}>")
        self.stack.pop()


def validate_html(text: str) -> None:
    checker = _TagChecker()
    checker.feed(text)
    checker.close()
    if checker.stack:
        raise _invalid(f"<{checker.stack[-1]}> is not closed")


def render_text(text: str, values: Mapping[str, str]) -> str:
    rendered = PREMIUM_EMOJI_RE.sub(r'<tg-emoji emoji-id="\2">\1</tg-emoji>', text)
    return VARIABLE_RE.sub(lambda m: html.escape(values.get(m.group(1)) or EMPTY_VALUE), rendered)
