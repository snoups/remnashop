import html
import re
from html.parser import HTMLParser
from typing import Final, Optional

from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError

PREMIUM_EMOJI_RE: Final[re.Pattern[str]] = re.compile(r"\[([^\[\]]{1,16})\]\(emoji:(\d{1,24})\)")
TELEGRAM_TEXT_LIMIT: Final[int] = 4096
TELEGRAM_CAPTION_LIMIT: Final[int] = 1024
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
_TAG_RE: Final[re.Pattern[str]] = re.compile(r"<[^<>]*>")


def telegram_length(text: str) -> int:
    # Telegram counts UTF-16 code units; premium emoji markup is sent as its glyph
    sent = PREMIUM_EMOJI_RE.sub(r"\1", text)
    return len(sent.encode("utf-16-le")) // 2


def html_text_length(text: str) -> int:
    return telegram_length(html.unescape(_TAG_RE.sub("", text)))


class _TagChecker(HTMLParser):
    def __init__(self, code: ErrorCode) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: list[str] = []
        self._code = code

    def invalid(self, reason: str) -> ValidationError:
        return ValidationError(f"Invalid HTML: {reason}", code=self._code)

    def handle_data(self, data: str) -> None:
        if "<" in data:
            raise self.invalid("bare < in text data must be escaped as &lt;")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag not in _ALLOWED_TAGS:
            raise self.invalid(f"<{tag}> is not supported")
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if not href.startswith(_URL_SCHEMES):
                raise self.invalid("link must start with https://, http:// or tg://")
        self.stack.append(tag)

    def handle_comment(self, data: str) -> None:
        raise self.invalid("comments are not supported")

    def handle_decl(self, decl: str) -> None:
        raise self.invalid("declarations are not supported")

    def handle_pi(self, data: str) -> None:
        raise self.invalid("processing instructions are not supported")

    def unknown_decl(self, data: str) -> None:
        raise self.invalid("declarations are not supported")

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack[-1] != tag:
            raise self.invalid(f"unexpected </{tag}>")
        self.stack.pop()


def validate_telegram_html(text: str, *, code: ErrorCode) -> None:
    checker = _TagChecker(code)
    checker.feed(text)
    checker.close()
    if checker.stack:
        raise checker.invalid(f"<{checker.stack[-1]}> is not closed")
