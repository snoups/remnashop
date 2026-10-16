import html
import re
from collections.abc import Callable
from html.parser import HTMLParser
from typing import Final, Optional

from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError

EMAIL_IMAGE_SRC_PREFIX: Final[str] = "bc-image:"
_ALLOWED_TAGS: Final[frozenset[str]] = frozenset(
    {
        "p",
        "h1",
        "h2",
        "h3",
        "b",
        "strong",
        "i",
        "em",
        "u",
        "s",
        "ul",
        "ol",
        "li",
        "blockquote",
        "hr",
        "br",
        "a",
        "img",
    }
)
_VOID_TAGS: Final[frozenset[str]] = frozenset({"hr", "br", "img"})
_BLOCK_TAGS: Final[frozenset[str]] = frozenset({"p", "h1", "h2", "h3", "li", "blockquote"})
_LINK_SCHEMES: Final[tuple[str, ...]] = ("https://", "http://", "mailto:")
_IMAGE_SRC_RE: Final[re.Pattern[str]] = re.compile(r"bc-image:([0-9]+)")
_UNSAFE_URL_CHAR_RE: Final[re.Pattern[str]] = re.compile(r"[\s\x00-\x1f\x7f]")
_EXTRA_NEWLINES_RE: Final[re.Pattern[str]] = re.compile(r"\n{3,}")
_ALLOWED_ATTRS: Final[dict[str, frozenset[str]]] = {
    "a": frozenset({"href", "data-button"}),
    "img": frozenset({"src", "alt"}),
}
_STYLES: Final[dict[str, str]] = {
    "p": "margin:0 0 12px;font-size:15px;line-height:1.5",
    "h1": "margin:0 0 12px;font-size:22px",
    "h2": "margin:0 0 12px;font-size:18px",
    "h3": "margin:0 0 12px;font-size:16px",
    "ul": "margin:0 0 12px;padding-left:20px",
    "ol": "margin:0 0 12px;padding-left:20px",
    "blockquote": "margin:0 0 12px;padding-left:12px;border-left:3px solid #e4e4e7;color:#52525b",
    "hr": "border:none;border-top:1px solid #e4e4e7;margin:16px 0",
    "img": "display:block;max-width:100%;height:auto;margin:0 0 12px",
    "a": "color:{accent}",
}
_BUTTON_STYLE: Final[str] = (
    "background:{accent};color:#fff;padding:10px 20px;border-radius:999px;"
    "text-decoration:none;display:inline-block"
)

_Attrs = list[tuple[str, Optional[str]]]


def _invalid(reason: str) -> ValidationError:
    return ValidationError(
        f"Invalid email HTML: {reason}", code=ErrorCode.BROADCAST_EMAIL_HTML_INVALID
    )


class _Walker(HTMLParser):
    # void tags never get an end tag, so subclasses only see their start
    def handle_startendtag(self, tag: str, attrs: _Attrs) -> None:
        self.handle_starttag(tag, attrs)


class _Validator(_Walker):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: list[str] = []

    def handle_data(self, data: str) -> None:
        if "<" in data:
            raise _invalid("bare < in text data must be escaped as &lt;")

    def handle_starttag(self, tag: str, attrs: _Attrs) -> None:
        if tag not in _ALLOWED_TAGS:
            raise _invalid(f"<{tag}> is not supported")
        allowed = _ALLOWED_ATTRS.get(tag, frozenset())
        values = dict(attrs)
        for name in values:
            if name not in allowed:
                raise _invalid(f"attribute {name} is not supported on <{tag}>")
        if tag == "a":
            href = values.get("href") or ""
            if not href.startswith(_LINK_SCHEMES) or _UNSAFE_URL_CHAR_RE.search(href):
                raise _invalid("link must be an https://, http:// or mailto: address")
        elif tag == "img":
            if not _IMAGE_SRC_RE.fullmatch(values.get("src") or ""):
                raise _invalid("image must reference an uploaded broadcast image")
        if tag not in _VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: _Attrs) -> None:
        if tag not in _VOID_TAGS:
            raise _invalid(f"<{tag}/> is not supported")
        self.handle_starttag(tag, attrs)

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


def validate_email_html(html: str) -> None:
    validator = _Validator()
    validator.feed(html)
    # close() silently drops a tag cut off at the end, so check what feed() left unparsed
    if validator.rawdata.startswith("<"):
        raise _invalid("incomplete tag at the end")
    validator.close()
    if validator.stack:
        raise _invalid(f"<{validator.stack[-1]}> is not closed")


class _ImageIds(_Walker):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[int] = set()

    def handle_starttag(self, tag: str, attrs: _Attrs) -> None:
        match = _IMAGE_SRC_RE.fullmatch(dict(attrs).get("src") or "") if tag == "img" else None
        if match:
            self.ids.add(int(match.group(1)))


def email_image_ids(html: str) -> set[int]:
    walker = _ImageIds()
    walker.feed(html)
    walker.close()
    return walker.ids


class _Styler(_Walker):
    def __init__(self, accent: str, image_src: Callable[[int], str]) -> None:
        super().__init__()
        self._accent = accent
        self._image_src = image_src
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(html.escape(data, quote=False))

    def handle_starttag(self, tag: str, attrs: _Attrs) -> None:
        if tag not in _ALLOWED_TAGS:
            return
        values = dict(attrs)
        attributes: list[tuple[str, str]] = []
        style = _STYLES.get(tag, "")
        if tag == "a":
            attributes.append(("href", values.get("href") or ""))
            style = _BUTTON_STYLE if "data-button" in values else style
        elif tag == "img":
            match = _IMAGE_SRC_RE.fullmatch(values.get("src") or "")
            attributes.append(("src", self._image_src(int(match.group(1))) if match else ""))
            attributes.append(("alt", values.get("alt") or ""))
        if style:
            attributes.append(("style", style.format(accent=self._accent)))
        rendered = "".join(
            f' {name}="{html.escape(value, quote=True)}"' for name, value in attributes
        )
        self.parts.append(f"<{tag}{rendered}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in _ALLOWED_TAGS and tag not in _VOID_TAGS:
            self.parts.append(f"</{tag}>")


def style_email_html(html: str, *, accent: str, image_src: Callable[[int], str]) -> str:
    styler = _Styler(accent, image_src)
    styler.feed(html)
    styler.close()
    return "".join(styler.parts)


class _TextExtractor(_Walker):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._links: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: _Attrs) -> None:
        values = dict(attrs)
        if tag == "a":
            href = values.get("href") or ""
            self._links.append(f": {href}" if "data-button" in values else f" ({href})")
        elif tag in ("br", "hr"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._links:
            self.parts.append(self._links.pop())
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")


def email_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    return _EXTRA_NEWLINES_RE.sub("\n\n", "".join(extractor.parts)).strip()
