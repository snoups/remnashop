from dataclasses import dataclass
from typing import Optional

from pydantic import Field

from app.core.constants import DEFAULT_BANNER_NAME
from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import (
    ButtonLinkType,
    ButtonStyleKind,
    DialogFlow,
    DialogWindowKind,
    Locale,
)


class DialogButtonDto(BaseDto, TimestampMixin):
    window_id: int
    row: int
    column: int
    text_key: str
    style: Optional[ButtonStyleKind] = None
    visibility_condition: Optional[str] = None
    link_type: ButtonLinkType
    action_key: Optional[str] = None
    target_window_key: Optional[str] = None
    url_value: Optional[str] = None
    is_hidden: bool = False
    # Shipped with a seed window; can be edited but never hidden.
    is_system: bool = False


class DialogWindowDto(BaseDto, TimestampMixin):
    key: str
    kind: DialogWindowKind
    flow: DialogFlow
    banner_name: Optional[str] = None
    name: Optional[str] = None
    is_enabled: bool = True
    position: int = 0
    slot: Optional[int] = None
    buttons: list[DialogButtonDto] = Field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class UpdateDialogWindowDto:
    # banner_name=None means both "keep the banner" and "drop it"; the flag
    # tells them apart
    banner_name: Optional[str] = None
    banner_name_provided: bool = False
    is_enabled: Optional[bool] = None
    name: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class DialogButtonInputDto:
    row: int
    column: int
    text_key: str
    link_type: ButtonLinkType
    style: Optional[ButtonStyleKind] = None
    visibility_condition: Optional[str] = None
    action_key: Optional[str] = None
    target_window_key: Optional[str] = None
    url_value: Optional[str] = None
    is_hidden: bool = False


@dataclass(frozen=True, kw_only=True)
class CreateCustomWindowDto:
    banner_name: Optional[str] = None
    name: Optional[str] = None
    position: int = 0


@dataclass(frozen=True, kw_only=True)
class DialogTextExportDto:
    locale: Locale
    message_id: str
    attribute_id: str
    value: str


@dataclass(frozen=True, kw_only=True)
class DialogWindowExportDto:
    key: str
    kind: DialogWindowKind
    banner_name: Optional[str]
    name: Optional[str] = None
    is_enabled: bool
    position: int
    buttons: list[DialogButtonInputDto]


@dataclass(frozen=True, kw_only=True)
class DialogExportDto:
    version: int
    windows: list[DialogWindowExportDto]
    texts: list[DialogTextExportDto]


@dataclass(frozen=True, kw_only=True)
class DialogCatalogDto:
    action_keys: list[str]
    condition_keys: list[str]
    variable_keys: list[str]
    text_variable_keys: list[str]
    # per window, on top of text_variable_keys; only windows that have any
    window_text_variable_keys: dict[str, list[str]]
    variable_categories: dict[str, str]
    seed_window_keys: list[str]
    navigable_window_keys: list[str]
    custom_window_limit: int


@dataclass(frozen=True, kw_only=True)
class CreateCustomDialogWindowDto:
    name: str
    # Every window starts on the shared banner; the inspector is where an
    # admin moves it to its own or turns it off.
    banner_name: Optional[str] = DEFAULT_BANNER_NAME


@dataclass(frozen=True, kw_only=True)
class UpdateDialogTextDto:
    locale: Locale
    message_id: str
    attribute_id: str
    value: str


@dataclass(frozen=True, kw_only=True)
class ConfigureDialogWindowDto:
    key: str
    banner_name: Optional[str] = None
    banner_name_provided: bool = False
    is_enabled: Optional[bool] = None
    name: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class UpdateDialogWindowButtonsDto:
    key: str
    buttons: list[DialogButtonInputDto]
