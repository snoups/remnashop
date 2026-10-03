import json
from typing import Any, Final, Literal, Optional
from urllib.parse import urlsplit

from loguru import logger
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

REPO_RAW_BASE: Final[str] = "https://raw.githubusercontent.com/remnashop/announcements/main/"
FEED_URL: Final[str] = REPO_RAW_BASE + "announcements.json"

ICONS: Final[frozenset[str]] = frozenset(
    {"info", "warning", "sparkles", "message", "gift", "telegram"}
)
_LINK_HOSTS: Final[frozenset[str]] = frozenset({"github.com", "t.me", "boosty.to", "remnashop.dev"})
_TITLE_MAX: Final[int] = 120
_TEXT_MAX: Final[int] = 1000
_URL_LABEL_MAX: Final[int] = 40
_SLIDES_MAX: Final[int] = 10
# segments start with [a-z0-9], so ".." and absolute paths can't match
_IMAGE_PATTERN: Final[str] = r"^[a-z0-9][a-z0-9_-]*(/[a-z0-9][a-z0-9_.-]*)*\.(webp|png|jpe?g)$"


class FeedError(Exception):
    pass


def _check_link(url: Optional[str]) -> Optional[str]:
    if url is None:
        return None
    if "\\" in url or any(c.isspace() or ord(c) < 0x20 for c in url):
        raise ValueError(f"link contains disallowed characters: {url}")
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in _LINK_HOSTS:
        raise ValueError(f"link must be https on an allowlisted host: {url}")
    if parts.username is not None or parts.password is not None:
        raise ValueError(f"link must not contain userinfo: {url}")
    try:
        port = parts.port
    except ValueError as error:
        raise ValueError(f"link has invalid port: {url}") from error
    if port is not None and port != 443:
        raise ValueError(f"link must use port 443 or default: {url}")
    return url


def _check_localized(value: dict[str, str], limit: int, *, required: bool) -> dict[str, str]:
    if required and not value:
        raise ValueError("at least one locale is required")
    if any("\x00" in text for text in (*value, *value.values())):
        raise ValueError("localized text contains NUL")
    if any(len(text) > limit for text in value.values()):
        raise ValueError(f"localized text longer than {limit}")
    return value


class FeedSlide(BaseModel):
    model_config = ConfigDict(extra="ignore")

    image: Optional[str] = Field(default=None, pattern=_IMAGE_PATTERN)
    text: dict[str, str]
    url: Optional[str] = None
    url_label: dict[str, str] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def _text(cls, value: dict[str, str]) -> dict[str, str]:
        return _check_localized(value, _TEXT_MAX, required=True)

    @field_validator("url")
    @classmethod
    def _url(cls, value: Optional[str]) -> Optional[str]:
        return _check_link(value)

    @field_validator("url_label")
    @classmethod
    def _url_label(cls, value: dict[str, str]) -> dict[str, str]:
        return _check_localized(value, _URL_LABEL_MAX, required=False)


class FeedItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,99}$")
    icon: str = "info"
    severity: Literal["info", "critical"] = "info"
    title: dict[str, str]
    text: dict[str, str] = Field(default_factory=dict)
    url: Optional[str] = None
    url_label: dict[str, str] = Field(default_factory=dict)
    roles: Optional[list[Literal["OWNER", "ADMIN"]]] = Field(default=None, min_length=1)
    versions: Optional[str] = Field(default=None, max_length=200)
    notify_at: AwareDatetime
    auto_open: bool = False
    slides: list[FeedSlide] = Field(default_factory=list, max_length=_SLIDES_MAX)

    @field_validator("icon", mode="before")
    @classmethod
    def _icon(cls, value: Any) -> str:
        return value if isinstance(value, str) and value in ICONS else "info"

    @field_validator("title")
    @classmethod
    def _title(cls, value: dict[str, str]) -> dict[str, str]:
        return _check_localized(value, _TITLE_MAX, required=True)

    @field_validator("text")
    @classmethod
    def _text(cls, value: dict[str, str]) -> dict[str, str]:
        return _check_localized(value, _TEXT_MAX, required=False)

    @field_validator("url")
    @classmethod
    def _url(cls, value: Optional[str]) -> Optional[str]:
        return _check_link(value)

    @field_validator("url_label")
    @classmethod
    def _url_label(cls, value: dict[str, str]) -> dict[str, str]:
        return _check_localized(value, _URL_LABEL_MAX, required=False)

    @field_validator("versions")
    @classmethod
    def _versions(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            SpecifierSet(value)
        except InvalidSpecifier as error:
            raise ValueError(f"invalid versions specifier: {value}") from error
        return value

    @model_validator(mode="after")
    def _auto_open_needs_slides(self) -> "FeedItem":
        if not self.slides:
            self.auto_open = False
        return self


def parse_feed(body: bytes) -> list[FeedItem]:
    try:
        raw = json.loads(body)
    except ValueError as error:
        raise FeedError(f"announcements feed is not JSON: {error}") from error
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
        raise FeedError("announcements feed has no items list")

    items: list[FeedItem] = []
    seen: set[str] = set()
    for entry in raw["items"]:
        try:
            item = FeedItem.model_validate(entry)
        except ValidationError as error:
            logger.warning(f"Announcement skipped: {error.errors(include_url=False)}")
            continue
        if item.id in seen:
            logger.warning(f"Announcement '{item.id}' skipped: duplicate id")
            continue
        seen.add(item.id)
        items.append(item)
    return items
