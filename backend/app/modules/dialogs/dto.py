from dataclasses import dataclass
from typing import Optional

from pydantic import Field

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import (
    BannerName,
    ButtonLinkType,
    ButtonStyleKind,
    DialogFlow,
    DialogWindowKind,
)


class DialogButtonDto(BaseDto, TimestampMixin):
    window_id: int
    row: int
    column: int
    text_key: str
    icon_custom_emoji_id: Optional[str] = None
    style: Optional[ButtonStyleKind] = None
    visibility_condition: Optional[str] = None
    link_type: ButtonLinkType
    action_key: Optional[str] = None
    target_window_key: Optional[str] = None
    url_value: Optional[str] = None
    is_hidden: bool = False


class DialogWindowDto(BaseDto, TimestampMixin):
    key: str
    kind: DialogWindowKind
    flow: DialogFlow
    banner_name: Optional[BannerName] = None
    is_enabled: bool = True
    position: int = 0
    buttons: list[DialogButtonDto] = Field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class UpdateDialogWindowDto:
    banner_name: Optional[BannerName] = None
    is_enabled: Optional[bool] = None


@dataclass(frozen=True, kw_only=True)
class DialogButtonInputDto:
    row: int
    column: int
    text_key: str
    link_type: ButtonLinkType
    icon_custom_emoji_id: Optional[str] = None
    style: Optional[ButtonStyleKind] = None
    visibility_condition: Optional[str] = None
    action_key: Optional[str] = None
    target_window_key: Optional[str] = None
    url_value: Optional[str] = None
    is_hidden: bool = False


@dataclass(frozen=True, kw_only=True)
class CreateCustomWindowDto:
    banner_name: Optional[BannerName] = None
    position: int = 0


@dataclass(frozen=True, kw_only=True)
class DialogCatalogDto:
    action_keys: list[str]
    condition_keys: list[str]
    variable_keys: list[str]
    seed_window_keys: list[str]
    navigable_window_keys: list[str]
