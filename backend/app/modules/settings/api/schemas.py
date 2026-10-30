import re
from typing import Annotated, Final, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from app.core.constants import INT64_MAX
from app.core.enums import AccessMode, CaptchaProvider, SmtpSecurity

_COMMAND_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_]{1,32}$")
# a Telegram username as typed: "name", "@name", "t.me/name" or "https://t.me/name"
_TELEGRAM_USERNAME: Final[re.Pattern[str]] = re.compile(
    r"^(?:@|(?:https?://)?t\.me/)?([A-Za-z0-9_]{4,32})/?$"
)
# no control characters (a line break above all): it lands in an email header
_HEADER_TEXT: Final[str] = r"^[^\x00-\x1f\x7f]*$"


class BotSettingsResponse(BaseModel):
    is_configured: bool
    is_proxy_configured: bool
    drop_pending_updates: bool


class SetBotProxyRequest(BaseModel):
    proxy_url: str = Field(min_length=1)


class BotStatusResponse(BaseModel):
    is_configured: bool
    is_running: bool
    webhook_url: Optional[str]
    pending_update_count: int
    error: Optional[str]


class UpdateBotSettingsRequest(BaseModel):
    token: Optional[str] = Field(default=None, min_length=1)
    secret_token: Optional[str] = Field(default=None, min_length=1)
    drop_pending_updates: Optional[bool] = None


class ShopSettingsResponse(BaseModel):
    max_active_subscriptions: Optional[int]
    device_single_reset_enabled: bool
    device_single_reset_cooldown_hours: int
    device_all_reset_enabled: bool
    device_all_reset_cooldown_hours: int
    link_reset_enabled: bool
    link_reset_cooldown_hours: int
    referral_reset_enabled: bool
    referral_reset_cooldown_hours: int
    support_telegram: Optional[str]
    support_url: Optional[str]


class UpdateShopSettingsRequest(BaseModel):
    max_active_subscriptions: Optional[int] = Field(default=None, ge=1)
    device_single_reset_enabled: Optional[bool] = None
    device_single_reset_cooldown_hours: Optional[int] = Field(default=None, ge=0)
    device_all_reset_enabled: Optional[bool] = None
    device_all_reset_cooldown_hours: Optional[int] = Field(default=None, ge=0)
    link_reset_enabled: Optional[bool] = None
    link_reset_cooldown_hours: Optional[int] = Field(default=None, ge=0)
    referral_reset_enabled: Optional[bool] = None
    referral_reset_cooldown_hours: Optional[int] = Field(default=None, ge=0)
    # null or "" clears either
    support_telegram: Optional[str] = None
    support_url: Optional[str] = Field(default=None, pattern=r"^https://.+", max_length=512)

    @field_validator("support_telegram", "support_url", mode="before")
    @classmethod
    def blank_is_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("support_telegram")
    @classmethod
    def telegram_username(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        match = _TELEGRAM_USERNAME.match(value.strip())
        if match is None:
            raise ValueError("support_telegram must be a Telegram username or a t.me link")
        return match.group(1)

    @model_validator(mode="after")
    def non_nullable_fields(self) -> "UpdateShopSettingsRequest":
        nullable = {"max_active_subscriptions", "support_telegram", "support_url"}
        for name in self.model_fields_set - nullable:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class BotCommandRequest(BaseModel):
    command: str = Field(pattern=_COMMAND_PATTERN.pattern)
    enabled: bool


class BotCommandResponse(BaseModel):
    command: str
    enabled: bool


class UpdateBotCommandsRequest(BaseModel):
    commands: list[BotCommandRequest]

    @model_validator(mode="after")
    def validate_unique_commands(self) -> "UpdateBotCommandsRequest":
        names = [item.command for item in self.commands]
        if len(names) != len(set(names)):
            raise ValueError("Command names must be unique")
        return self


class BotCommandsResponse(BaseModel):
    commands: list[BotCommandResponse]


class UpdateBotCommandsResponse(BotCommandsResponse):
    telegram_sync_failed: bool


class BotLogsResponse(BaseModel):
    lines: list[str]


class OAuthSettingsResponse(BaseModel):
    is_github_configured: bool
    github_enabled: bool
    is_telegram_configured: bool
    telegram_enabled: bool
    is_google_configured: bool
    is_yandex_configured: bool
    is_oidc_configured: bool
    oidc_enabled: bool
    oidc_display_name: Optional[str] = None
    password_login_enabled: bool
    is_passkey_configured: bool
    passkey_enabled: bool
    passkey_rp_id: Optional[str] = None
    passkey_origin: Optional[str] = None


class UpdateOAuthSettingsRequest(BaseModel):
    github_client_id: Optional[str] = Field(default=None, min_length=1)
    github_client_secret: Optional[str] = Field(default=None, min_length=1)
    github_enabled: Optional[bool] = None
    telegram_client_id: Optional[str] = Field(default=None, min_length=1)
    telegram_client_secret: Optional[str] = Field(default=None, min_length=1)
    telegram_enabled: Optional[bool] = None
    google_client_id: Optional[str] = Field(default=None, min_length=1)
    google_client_secret: Optional[str] = Field(default=None, min_length=1)
    yandex_client_id: Optional[str] = Field(default=None, min_length=1)
    yandex_client_secret: Optional[str] = Field(default=None, min_length=1)
    oidc_issuer_url: Optional[str] = Field(default=None, pattern=r"^https://.+", max_length=512)
    oidc_client_id: Optional[str] = Field(default=None, min_length=1)
    oidc_client_secret: Optional[str] = Field(default=None, min_length=1)
    oidc_display_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    oidc_enabled: Optional[bool] = None
    password_login_enabled: Optional[bool] = None
    passkey_enabled: Optional[bool] = None
    passkey_rp_id: Optional[str] = Field(default=None, min_length=1, max_length=255)
    passkey_origin: Optional[str] = Field(default=None, pattern=r"^https?://.+", max_length=512)


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


class AccessSettingsResponse(BaseModel):
    mode: AccessMode
    registration_enabled: bool
    payments_enabled: bool


class UpdateAccessSettingsRequest(BaseModel):
    mode: Optional[AccessMode] = None
    registration_enabled: Optional[bool] = None
    payments_enabled: Optional[bool] = None


class EmailSettingsResponse(BaseModel):
    host: Optional[str]
    port: int
    security: SmtpSecurity
    username: Optional[str]
    is_password_set: bool
    from_address: Optional[str]
    from_name: Optional[str]
    is_configured: bool
    bulk_host: Optional[str]
    bulk_port: int
    bulk_security: SmtpSecurity
    bulk_username: Optional[str]
    is_bulk_password_set: bool
    bulk_from_address: Optional[str]
    bulk_from_name: Optional[str]
    bulk_rate_per_minute: int
    is_bulk_configured: bool


class UpdateEmailSettingsRequest(BaseModel):
    host: Optional[str] = Field(None, min_length=1, max_length=255)
    port: Optional[int] = Field(None, ge=1, le=65535)
    security: Optional[SmtpSecurity] = None
    username: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, max_length=1024)
    from_address: Optional[str] = Field(
        None, min_length=1, max_length=255, pattern=r"^[^@\s]+@[^@\s]+$"
    )
    # a line break in a header value makes every send raise
    from_name: Optional[str] = Field(None, max_length=100, pattern=_HEADER_TEXT)
    bulk_host: Optional[str] = Field(None, min_length=1, max_length=255)
    bulk_port: Optional[int] = Field(None, ge=1, le=65535)
    bulk_security: Optional[SmtpSecurity] = None
    bulk_username: Optional[str] = Field(None, max_length=255)
    bulk_password: Optional[str] = Field(None, max_length=1024)
    bulk_from_address: Optional[str] = Field(
        None, min_length=1, max_length=255, pattern=r"^[^@\s]+@[^@\s]+$"
    )
    bulk_from_name: Optional[str] = Field(None, max_length=100, pattern=_HEADER_TEXT)
    bulk_rate_per_minute: Optional[int] = Field(None, ge=1, le=1000)


class CabinetAuthSettingsResponse(BaseModel):
    telegram_enabled: bool
    telegram_oauth_enabled: bool
    google_enabled: bool
    yandex_enabled: bool
    email_enabled: bool
    restrict_email_domains: bool
    allowed_email_domains: list[str]
    captcha_enabled: bool
    captcha_provider: CaptchaProvider
    captcha_site_key: Optional[str]
    is_captcha_configured: bool


class UpdateCabinetAuthSettingsRequest(BaseModel):
    telegram_enabled: Optional[bool] = None
    telegram_oauth_enabled: Optional[bool] = None
    google_enabled: Optional[bool] = None
    yandex_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    restrict_email_domains: Optional[bool] = None
    allowed_email_domains: Optional[list[str]] = None
    captcha_enabled: Optional[bool] = None
    captcha_provider: Optional[CaptchaProvider] = None
    captcha_site_key: Optional[str] = Field(default=None, min_length=1, max_length=255)
    captcha_secret_key: Optional[str] = Field(default=None, min_length=1, max_length=255)

    @field_validator("allowed_email_domains")
    @classmethod
    def _normalize_domains(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return None
        return list(
            dict.fromkeys(d for d in (item.strip().lstrip("@").lower() for item in value) if d)
        )


class BotRequirementsResponse(BaseModel):
    channel_required: bool
    channel_id: Optional[int]
    channel_url: Optional[str]
    trial_channel_guard: bool


class UpdateBotRequirementsRequest(BaseModel):
    channel_required: bool = False
    channel_id: Optional[int] = Field(default=None, ge=-INT64_MAX - 1, le=INT64_MAX)
    channel_url: Optional[HttpUrl] = None
    trial_channel_guard: bool = False


class CabinetSettingsResponse(BaseModel):
    max_active_subscriptions: Optional[int]
    device_single_reset_enabled: bool
    device_all_reset_enabled: bool
    device_all_reset_cooldown_hours: int
    link_reset_enabled: bool
    bot_username: Optional[str]
    support_telegram: Optional[str]
    support_url: Optional[str]
