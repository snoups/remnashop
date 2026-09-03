import re
from typing import Annotated, Final, Optional

from pydantic import BaseModel, Field, model_validator

from app.core.enums import Locale

_COMMAND_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_]{1,32}$")


class BotSettingsResponse(BaseModel):
    is_configured: bool
    drop_pending_updates: bool
    banners_enabled: bool


class UpdateBotSettingsRequest(BaseModel):
    token: Optional[str] = Field(default=None, min_length=1)
    secret_token: Optional[str] = Field(default=None, min_length=1)
    drop_pending_updates: Optional[bool] = None
    banners_enabled: Optional[bool] = None


class ShopSettingsResponse(BaseModel):
    max_active_subscriptions: Optional[int]


class UpdateShopSettingsRequest(BaseModel):
    max_active_subscriptions: Optional[int] = Field(default=None, ge=1)


class BotCommandItem(BaseModel):
    command: str = Field(pattern=_COMMAND_PATTERN.pattern)
    enabled: bool


class UpdateBotCommandsRequest(BaseModel):
    commands: list[BotCommandItem]

    @model_validator(mode="after")
    def validate_unique_commands(self) -> "UpdateBotCommandsRequest":
        names = [item.command for item in self.commands]
        if len(names) != len(set(names)):
            raise ValueError("Command names must be unique")
        return self


class UpdateBotCommandsResponse(BaseModel):
    commands: list[BotCommandItem]
    telegram_sync_failed: bool


class OAuthSettingsResponse(BaseModel):
    is_github_configured: bool
    is_github_enabled: bool
    is_telegram_configured: bool
    is_telegram_enabled: bool
    is_oidc_configured: bool
    is_oidc_enabled: bool
    oidc_display_name: Optional[str] = None
    is_password_login_enabled: bool


class UpdateOAuthSettingsRequest(BaseModel):
    github_client_id: Optional[str] = Field(default=None, min_length=1)
    github_client_secret: Optional[str] = Field(default=None, min_length=1)
    github_enabled: Optional[bool] = None
    telegram_client_id: Optional[str] = Field(default=None, min_length=1)
    telegram_client_secret: Optional[str] = Field(default=None, min_length=1)
    telegram_enabled: Optional[bool] = None
    oidc_issuer_url: Optional[str] = Field(default=None, pattern=r"^https://.+", max_length=512)
    oidc_client_id: Optional[str] = Field(default=None, min_length=1)
    oidc_client_secret: Optional[str] = Field(default=None, min_length=1)
    oidc_display_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    oidc_enabled: Optional[bool] = None
    password_login_enabled: Optional[bool] = None


class ActiveLocalesResponse(BaseModel):
    active: list[Locale]
    available: list[Locale]


class AddLocaleRequest(BaseModel):
    locale: Locale


class AppearanceResponse(BaseModel):
    brand_name: Optional[str] = None
    primary_color: Optional[str] = None
    shader_palette: Optional[list[str]] = None
    shader_enabled: bool
    has_logo: bool
    has_favicon: bool


class UpdateAppearanceRequest(BaseModel):
    brand_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    primary_color: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    shader_palette: Optional[list[Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]]] = Field(
        default=None, min_length=4, max_length=4
    )
    shader_enabled: Optional[bool] = None
