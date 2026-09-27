from typing import Optional

from pydantic import BaseModel, Field

from app.core.constants import BANNER_NAME_PATTERN, DEFAULT_BANNER_NAME
from app.core.enums import (
    ButtonLinkType,
    ButtonStyleKind,
    DialogFlow,
    DialogWindowKind,
    Locale,
)


class DialogButtonItem(BaseModel):
    id: int
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
    is_system: bool = False


class DialogWindowResponse(BaseModel):
    key: str
    kind: DialogWindowKind
    flow: DialogFlow
    banner_name: Optional[str] = Field(default=None, max_length=160, pattern=BANNER_NAME_PATTERN)
    name: Optional[str] = None
    is_enabled: bool
    position: int
    text_keys: list[str]
    buttons: list[DialogButtonItem]


class DialogCatalogResponse(BaseModel):
    action_keys: list[str]
    condition_keys: list[str]
    variable_keys: list[str]
    text_variable_keys: list[str]
    seed_window_keys: list[str]
    navigable_window_keys: list[str]
    custom_window_limit: int


class UpdateDialogWindowRequest(BaseModel):
    banner_name: Optional[str] = Field(default=None, max_length=160, pattern=BANNER_NAME_PATTERN)
    is_enabled: Optional[bool] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)


class DialogButtonInput(BaseModel):
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    text_key: str = Field(min_length=1, max_length=64)
    link_type: ButtonLinkType
    style: Optional[ButtonStyleKind] = None
    visibility_condition: Optional[str] = Field(default=None, max_length=64)
    action_key: Optional[str] = Field(default=None, max_length=64)
    target_window_key: Optional[str] = Field(default=None, max_length=128)
    url_value: Optional[str] = Field(default=None, max_length=2048)
    is_hidden: bool = False


class ReplaceButtonsRequest(BaseModel):
    buttons: list[DialogButtonInput]


class CreateCustomWindowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # Omitting it means the shared banner; sending null explicitly means none.
    banner_name: Optional[str] = Field(
        default=DEFAULT_BANNER_NAME, max_length=160, pattern=BANNER_NAME_PATTERN
    )


class DialogTextExportItem(BaseModel):
    locale: Locale
    message_id: str = Field(min_length=1, max_length=128)
    attribute_id: str = Field(default="", max_length=128)
    value: str = Field(max_length=4096)


class DialogWindowExportItem(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9._-]+$", max_length=128)
    kind: DialogWindowKind
    banner_name: Optional[str] = Field(default=None, max_length=160, pattern=BANNER_NAME_PATTERN)
    name: Optional[str] = Field(default=None, max_length=128)
    is_enabled: bool = True
    position: int = Field(default=0, ge=0)
    buttons: list[DialogButtonInput] = Field(default_factory=list)


class DialogExportPayload(BaseModel):
    version: int
    windows: list[DialogWindowExportItem]
    texts: list[DialogTextExportItem] = Field(default_factory=list)


class UpdateDialogTextRequest(BaseModel):
    value: str = Field(max_length=4096)


class DialogTextResponse(BaseModel):
    locale: Locale
    message_id: str
    value: str
    default_value: str
