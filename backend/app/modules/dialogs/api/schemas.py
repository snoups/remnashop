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


class DialogButtonResponse(BaseModel):
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
    banner_name: Optional[str] = None
    name: Optional[str] = None
    is_enabled: bool
    position: int
    text_keys: list[str]
    buttons: list[DialogButtonResponse]


class DialogCatalogResponse(BaseModel):
    action_keys: list[str]
    condition_keys: list[str]
    variable_keys: list[str]
    text_variable_keys: list[str]
    window_text_variable_keys: dict[str, list[str]]
    variable_categories: dict[str, str]
    seed_window_keys: list[str]
    navigable_window_keys: list[str]
    custom_window_limit: int


class UpdateDialogWindowRequest(BaseModel):
    banner_name: Optional[str] = Field(default=None, max_length=160, pattern=BANNER_NAME_PATTERN)
    is_enabled: Optional[bool] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)


class DialogButtonRequest(BaseModel):
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
    buttons: list[DialogButtonRequest]


class CreateCustomWindowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # Omitting it means the shared banner; sending null explicitly means none.
    banner_name: Optional[str] = Field(
        default=DEFAULT_BANNER_NAME, max_length=160, pattern=BANNER_NAME_PATTERN
    )


class DialogTextImportRequest(BaseModel):
    locale: Locale
    message_id: str = Field(min_length=1, max_length=128)
    attribute_id: str = Field(default="", max_length=128)
    value: str = Field(max_length=4096)


class DialogTextExportResponse(BaseModel):
    locale: Locale
    message_id: str
    attribute_id: str
    value: str


class DialogWindowImportRequest(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9._-]+$", max_length=128)
    kind: DialogWindowKind
    banner_name: Optional[str] = Field(default=None, max_length=160, pattern=BANNER_NAME_PATTERN)
    name: Optional[str] = Field(default=None, max_length=128)
    is_enabled: bool = True
    position: int = Field(default=0, ge=0)
    buttons: list[DialogButtonRequest] = Field(default_factory=list)


class DialogButtonExportResponse(BaseModel):
    row: int
    column: int
    text_key: str
    link_type: ButtonLinkType
    style: Optional[ButtonStyleKind] = None
    visibility_condition: Optional[str] = None
    action_key: Optional[str] = None
    target_window_key: Optional[str] = None
    url_value: Optional[str] = None
    is_hidden: bool


class DialogWindowExportResponse(BaseModel):
    key: str
    kind: DialogWindowKind
    banner_name: Optional[str] = None
    name: Optional[str] = None
    is_enabled: bool
    position: int
    buttons: list[DialogButtonExportResponse]


class DialogExportResponse(BaseModel):
    version: int
    windows: list[DialogWindowExportResponse]
    texts: list[DialogTextExportResponse]


class DialogImportRequest(BaseModel):
    version: int
    windows: list[DialogWindowImportRequest]
    texts: list[DialogTextImportRequest] = Field(default_factory=list)


class UpdateDialogTextRequest(BaseModel):
    value: str = Field(max_length=4096)


class DialogTextResponse(BaseModel):
    locale: Locale
    message_id: str
    value: str
    default_value: str


class DialogWindowListResponse(BaseModel):
    items: list[DialogWindowResponse]
    total: int
