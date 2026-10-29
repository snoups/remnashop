"""The connect guide catalog: platform → apps → steps → buttons.

Validated on every write (the dashboard's PUT and the built-in default alike), so the cabinet can
render whatever it reads back without second-guessing it. A deep link is the one value that leaves
the cabinet as an address the browser opens, hence the scheme rules below.
"""

import re
from typing import Annotated, Final, Literal, Optional, Union
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from app.core.enums import Locale

SUBSCRIPTION_LINK_TOKEN: Final[str] = "{{SUBSCRIPTION_LINK}}"

# never an app import: web addresses are `external` buttons, the rest run code or read files
FORBIDDEN_DEEP_LINK_SCHEMES: Final[frozenset[str]] = frozenset(
    {"http", "https", "javascript", "data", "vbscript", "file", "blob", "about", "intent"}
)

# RFC 3986 scheme
_SCHEME: Final[re.Pattern[str]] = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")

PlatformId = Literal["ios", "android", "windows", "macos", "linux", "androidtv", "appletv"]
StepIcon = Literal[
    "download", "plus", "power", "settings", "check", "link", "qr", "info", "shield", "globe"
]

_Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
_Paragraph = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
_Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
_Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")]


def _not_empty(value: dict[Locale, str]) -> dict[Locale, str]:
    if not value:
        raise ValueError("at least one language is required")
    return value


LocalizedLine = Annotated[dict[Locale, _Line], AfterValidator(_not_empty)]
LocalizedParagraph = Annotated[dict[Locale, _Paragraph], AfterValidator(_not_empty)]


class _Value(BaseModel):
    model_config = ConfigDict(frozen=True)


class ExternalButton(_Value):
    kind: Literal["external"]
    label: LocalizedLine
    url: _Address

    @field_validator("url")
    @classmethod
    def _https_only(cls, url: str) -> str:
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.netloc:
            raise ValueError("must be an https:// address")
        return url


class DeepLinkButton(_Value):
    kind: Literal["deep_link"]
    label: LocalizedLine
    # {{SUBSCRIPTION_LINK}} becomes the customer's link, as is (`raw`) or percent-encoded
    template: _Address
    encode: Literal["raw", "component"]

    @field_validator("template")
    @classmethod
    def _app_scheme(cls, template: str) -> str:
        if SUBSCRIPTION_LINK_TOKEN not in template:
            raise ValueError(f"must contain {SUBSCRIPTION_LINK_TOKEN}")
        match = _SCHEME.match(template)
        if match is None:
            raise ValueError("must start with an app scheme, like happ://")
        if match[1].lower() in FORBIDDEN_DEEP_LINK_SCHEMES:
            raise ValueError(f"the {match[1]}: scheme is not allowed")
        return template


class CopyLinkButton(_Value):
    kind: Literal["copy_link"]
    label: LocalizedLine


ConnectButton = Annotated[
    Union[ExternalButton, DeepLinkButton, CopyLinkButton], Field(discriminator="kind")
]


class ConnectStep(_Value):
    title: LocalizedLine
    body: Optional[LocalizedParagraph] = None
    icon: StepIcon
    buttons: list[ConnectButton] = Field(default=[], max_length=4)


class ConnectApp(_Value):
    id: _Slug
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    featured: bool = False
    steps: list[ConnectStep] = Field(min_length=1, max_length=10)


class ConnectPlatform(_Value):
    id: PlatformId
    apps: list[ConnectApp] = Field(min_length=1, max_length=12)

    @field_validator("apps")
    @classmethod
    def _apps_unique(cls, apps: list[ConnectApp]) -> list[ConnectApp]:
        if len({app.id for app in apps}) != len(apps):
            raise ValueError("app ids must be unique within a platform")
        if sum(app.featured for app in apps) > 1:
            raise ValueError("at most one recommended app per platform")
        return apps


class ConnectCatalog(_Value):
    platforms: list[ConnectPlatform] = Field(default=[], max_length=7)

    @field_validator("platforms")
    @classmethod
    def _platforms_unique(cls, platforms: list[ConnectPlatform]) -> list[ConnectPlatform]:
        if len({platform.id for platform in platforms}) != len(platforms):
            raise ValueError("each platform may appear once")
        return platforms
