from typing import Optional

from pydantic import BaseModel, Field

from app.core.enums import (
    BannerName,
    ButtonLinkType,
    ButtonStyleKind,
    DialogFlow,
    DialogWindowKind,
    Locale,
)


class DialogButtonItem(BaseModel):
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


class DialogWindowResponse(BaseModel):
    key: str
    kind: DialogWindowKind
    flow: DialogFlow
    banner_name: Optional[BannerName] = None
    is_enabled: bool
    position: int
    buttons: list[DialogButtonItem]


class DialogCatalogResponse(BaseModel):
    action_keys: list[str]
    condition_keys: list[str]
    variable_keys: list[str]
    text_variable_keys: list[str]
    seed_window_keys: list[str]
    navigable_window_keys: list[str]


class UpdateDialogWindowRequest(BaseModel):
    banner_name: Optional[BannerName] = None
    is_enabled: Optional[bool] = None


class DialogButtonInput(BaseModel):
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    text_key: str = Field(min_length=1, max_length=64)
    link_type: ButtonLinkType
    icon_custom_emoji_id: Optional[str] = Field(default=None, max_length=32)
    style: Optional[ButtonStyleKind] = None
    visibility_condition: Optional[str] = Field(default=None, max_length=64)
    action_key: Optional[str] = Field(default=None, max_length=64)
    target_window_key: Optional[str] = Field(default=None, max_length=128)
    url_value: Optional[str] = None
    is_hidden: bool = False


class ReplaceButtonsRequest(BaseModel):
    buttons: list[DialogButtonInput]


class CreateCustomWindowRequest(BaseModel):
    title_text: str = Field(min_length=1, max_length=4096)
    banner_name: Optional[BannerName] = None


class UpdateDialogTextRequest(BaseModel):
    value: str = Field(max_length=4096)


class DialogTextResponse(BaseModel):
    locale: Locale
    message_id: str
    value: str
    default_value: str
